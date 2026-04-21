from typing import List, Optional, Tuple

from config.config_loader import load_validator_config
from domain.core.enums import Sectors
from domain.core.missing import MissingReason
from domain.core.missing_registry import MissingValueRegistry
from domain.metrics.stock import StockMetrics
from domain.valuation.policies import (
    CheckFactor,
    FactorSeverity,
    ValuationChecker,
    ValuationCheckResult,
)

_cfg = load_validator_config("dcf")

# ---------------------------------------------------------------------------
# BUG-1 fix: score thresholds aligned across all validators.
#
# Old: block at >10  (two CRITICALs × weight=3 = 6 → still ran DCF)
# New: block at >=6  (two CRITICALs → blocked immediately)
#
# Hard-block sentinel: when both FCF_ttm and last_year_fcf are negative the
# DCF is mathematically invalid regardless of weighting — force score to 99.
# ---------------------------------------------------------------------------
_SCORE_BLOCK_THRESHOLD = 6   # ≥ this → skip valuation

# Hard-block weight assigned when the FCF base itself invalidates DCF.
_DUAL_NEGATIVE_FCF_WEIGHT = 99


def _sector(stock_metrics: StockMetrics) -> Optional[Sectors]:
    return stock_metrics.profile.sector if stock_metrics.profile else None


class DCFChecker(ValuationChecker):

    CRITICAL_WEIGHT = 3
    WARNING_WEIGHT  = 1

    def __init__(
        self,
        stock_metrics: StockMetrics,
        registry: Optional[MissingValueRegistry] = None,
    ):
        self._metrics  = stock_metrics
        self._registry = registry
        self._factors: List[CheckFactor] = []
        self._score = 0

    def _add_factor(self, name, message, severity, value=None, weight_override=None):
        if weight_override is not None:
            weight = weight_override
        else:
            weight = (
                self.CRITICAL_WEIGHT if severity == FactorSeverity.CRITICAL
                else self.WARNING_WEIGHT if severity == FactorSeverity.WARNING
                else 0
            )
        self._factors.append(
            CheckFactor(name=name, message=message, severity=severity, weight=weight, value=value)
        )
        self._score += weight

    def _interpret_score(self) -> Tuple[bool, str]:
        score = self._score
        if score == 0:
            return True,  "Perfectly suitable for DCF."
        if 1 <= score <= 2:
            return True,  "Minor warnings, generally suitable for DCF."
        if 3 <= score <= 5:
            return True,  "Minor concerns, DCF should be interpreted carefully."
        if score == _DUAL_NEGATIVE_FCF_WEIGHT:
            return False, "DCF invalid: both TTM and prior-year FCF are negative. Cannot project from a negative base."
        return False, "Significant risk, DCF may be unreliable."

    def _missing_severity(
        self,
        model: str,
        field: str,
        default: FactorSeverity = FactorSeverity.CRITICAL,
    ) -> FactorSeverity:
        if self._registry is None:
            return default
        entry = self._registry.get(model, field)
        if entry is not None and entry.reason == MissingReason.NOT_APPLICABLE:
            return FactorSeverity.WARNING
        return default

    def _check_free_cash_flow(self):
        sector           = _sector(self._metrics)
        fcf_ttm          = self._metrics.cash_flow.fcf_ttm
        last_quarter_fcf = self._metrics.cash_flow.last_quarter_fcf
        last_year_fcf    = self._metrics.cash_flow.last_year_fcf

        fcf_negative_severity = (
            FactorSeverity.WARNING
            if sector == Sectors.REAL_ESTATE
            else FactorSeverity.CRITICAL
        )

        # BUG-1 fix: hard-block when BOTH TTM and prior-year FCF are negative.
        # A negative seed FCF compounds further negative — the DCF output is
        # meaningless regardless of how the WACC and growth rates are set.
        if fcf_ttm < 0 and last_year_fcf < 0:
            self._add_factor(
                "Dual Negative FCF — DCF Invalid",
                f"Both TTM FCF ({fcf_ttm:,.0f}) and prior-year FCF ({last_year_fcf:,.0f}) "
                f"are negative. A DCF compounding from a negative base produces negative "
                f"intrinsic values that are financially meaningless. "
                f"Consider using normalized FCF or a different valuation model.",
                FactorSeverity.CRITICAL,
                fcf_ttm,
                weight_override=_DUAL_NEGATIVE_FCF_WEIGHT,
            )
            return  # no point adding further FCF sub-checks

        if fcf_ttm == 0.0 and self._registry is not None and \
                self._registry.has_missing_field("CashFlow", "fcf_ttm"):
            sev = self._missing_severity("CashFlow", "fcf_ttm")
            entry = self._registry.get("CashFlow", "fcf_ttm")
            detail = entry.detail if entry else "Free Cash Flow (TTM) data is missing."
            self._add_factor("Missing FCF (TTM)", detail, sev)
        elif fcf_ttm == 0.0 and self._registry is None:
            self._add_factor(
                "Missing FCF (TTM)",
                "Free Cash Flow (TTM) is zero or missing.",
                FactorSeverity.CRITICAL,
            )
        elif fcf_ttm < 0:
            message = f"Free Cash Flow (TTM) is negative: {fcf_ttm:,.0f}"
            if last_quarter_fcf > 0:
                self._add_factor(
                    "Negative TTM FCF (Temporary)",
                    f"{message}, but last quarter FCF is positive, suggesting temporary cash burn.",
                    FactorSeverity.WARNING,
                    fcf_ttm,
                )
            else:
                self._add_factor(
                    "Negative TTM FCF",
                    message,
                    fcf_negative_severity,
                    fcf_ttm,
                )

        if last_year_fcf == 0.0 and self._registry is not None and \
                self._registry.has_missing_field("CashFlow", "last_year_fcf"):
            sev = self._missing_severity("CashFlow", "last_year_fcf")
            self._add_factor("Missing Last Year FCF", "Last Year FCF data is missing.", sev)
        elif last_year_fcf < 0:
            self._add_factor(
                "Negative Last Year FCF",
                f"Last Year FCF is negative: {last_year_fcf:,.0f}",
                fcf_negative_severity,
                last_year_fcf,
            )

    def _check_profitability(self):
        eps_ttm          = self._metrics.market_data.eps_ttm if self._metrics.market_data else 0.0
        net_income_ttm   = self._metrics.financials.net_income_ttm
        operating_cf_ttm = self._metrics.cash_flow.operating_cf_ttm

        if eps_ttm <= 0:
            sev = self._missing_severity("MarketData", "eps_ttm") \
                if eps_ttm == 0.0 else FactorSeverity.CRITICAL
            self._add_factor(
                "Negative EPS (TTM)",
                f"Earnings Per Share (TTM) is zero, negative, or missing: {eps_ttm}",
                sev,
                eps_ttm,
            )

        if net_income_ttm == 0.0 and self._registry is not None and \
                self._registry.has_missing_field("Financials", "net_income_ttm"):
            self._add_factor("Missing Net Income (TTM)", "Net Income (TTM) data is missing.", FactorSeverity.CRITICAL)
        elif net_income_ttm <= 0 and net_income_ttm != 0.0:
            self._add_factor(
                "Negative Net Income (TTM)",
                f"Net Income (TTM) is zero or negative: {net_income_ttm:,.0f}",
                FactorSeverity.CRITICAL,
                net_income_ttm,
            )

        if operating_cf_ttm == 0.0 and self._registry is not None and \
                self._registry.has_missing_field("CashFlow", "operating_cf_ttm"):
            self._add_factor("Missing Operating CF", "Operating Cash Flow (TTM) data is missing.", FactorSeverity.CRITICAL)
        elif operating_cf_ttm < 0:
            self._add_factor(
                "Negative Operating CF",
                f"Operating Cash Flow (TTM) is negative: {operating_cf_ttm:,.0f}",
                FactorSeverity.CRITICAL,
                operating_cf_ttm,
            )

    def _check_risk_and_stability(self):
        sector      = _sector(self._metrics)
        market_data = self._metrics.market_data
        valuation   = self._metrics.valuation

        cost_of_debt  = valuation.cost_of_debt if valuation else 0.0
        cod_threshold = _cfg.get_float("cost_of_debt_critical", sector, default=0.20)
        if cost_of_debt > cod_threshold:
            self._add_factor(
                "High Cost of Debt",
                (f"Cost of Debt ({cost_of_debt:.1%}) exceeds the sector threshold "
                 f"of {cod_threshold:.1%} for {sector.value if sector else 'unknown'}, "
                 "increasing WACC risk."),
                FactorSeverity.CRITICAL,
                cost_of_debt,
            )
        # Also flag when cost_of_debt was zeroed due to ceiling breach (BUG-6)
        elif cost_of_debt == 0.0 and valuation is not None:
            # Check if the registry or diagnostics flagged a ceiling breach
            if self._registry is not None:
                entry = self._registry.get("Valuation", "cost_of_debt")
                if entry is not None and entry.reason == MissingReason.DERIVED_FAILED:
                    self._add_factor(
                        "Cost of Debt Unusable (Data Quality)",
                        f"Cost of debt could not be computed reliably: {entry.detail}",
                        FactorSeverity.CRITICAL,
                        0.0,
                    )

        tax_rate = valuation.corporate_tax_rate if valuation else 0.0
        if tax_rate < 0:
            self._add_factor(
                "Negative Tax Rate",
                f"Corporate Tax Rate is negative: {tax_rate:.2%}",
                FactorSeverity.WARNING,
                tax_rate,
            )

        beta           = market_data.beta if market_data else 1.0
        beta_threshold = _cfg.get_float("beta_warning", sector, default=2.0)
        if beta > beta_threshold:
            self._add_factor(
                "High Beta",
                (f"Stock Beta ({beta:.2f}) exceeds the sector threshold of "
                 f"{beta_threshold:.1f} for {sector.value if sector else 'unknown'}, "
                 "suggesting elevated volatility and forecast uncertainty."),
                FactorSeverity.WARNING,
                beta,
            )

        market_cap    = market_data.market_cap if market_data else 0.0
        cap_threshold = _cfg.get_int("market_cap_warning", sector, default=500_000_000)
        if market_cap > 0 and market_cap < cap_threshold:
            self._add_factor(
                "Small Market Cap",
                (f"Market cap (${market_cap:,.0f}) is below the sector threshold of "
                 f"${cap_threshold:,.0f} for {sector.value if sector else 'unknown'}, "
                 "which may reduce long-term forecast reliability."),
                FactorSeverity.WARNING,
                market_cap,
            )

    def _check_capex_spike(self):
        """BUG-5 fix: warn when a capex spike has materially distorted FCF_ttm.

        If normalized FCF is available, the company remains DCF-eligible because
        the valuation path can use the adjusted seed instead of the raw spike.
        """
        valuation = self._metrics.valuation
        if valuation is not None and valuation.capex_spike_detected:
            normalized = valuation.normalized_fcf
            norm_str = f"{normalized/1e9:.1f}B" if normalized is not None else "unknown"
            severity = FactorSeverity.WARNING if normalized is not None else FactorSeverity.CRITICAL
            message = (
                f"TTM capex is anomalously high vs. historical median — likely one-time "
                f"infrastructure investment rather than ongoing maintenance capex. "
            )
            if normalized is not None:
                message += (
                    f"DCF can use normalized FCF ≈ {norm_str} instead of raw FCF_ttm. "
                    f"Intrinsic values may be understated if raw FCF is used."
                )
            else:
                message += (
                    f"Normalized FCF is unavailable, so raw FCF_ttm may be materially "
                    f"distorted. Intrinsic values may be understated."
                )
            self._add_factor(
                "Capex Spike Detected",
                message,
                severity,
            )

    def _check_growth_stage(self):
        revenue_growth_rate = self._metrics.financials.revenue_growth_rate
        net_income_ttm      = self._metrics.financials.net_income_ttm

        if revenue_growth_rate > 0.2 and net_income_ttm < 0:
            self._add_factor(
                "Growth-Stage Startup",
                (f"High revenue growth ({revenue_growth_rate * 100:.2f}%) with negative "
                 "net income indicates a potentially high-risk, high-growth startup phase."),
                FactorSeverity.WARNING,
                revenue_growth_rate,
            )

    def evaluate(self) -> ValuationCheckResult:
        self._check_free_cash_flow()
        # Short-circuit: if the hard-block sentinel was triggered (dual-negative FCF)
        # there is no point running further checks — the model is unconditionally invalid.
        if self._score >= _DUAL_NEGATIVE_FCF_WEIGHT:
            is_suitable, interpretation = self._interpret_score()
            return ValuationCheckResult(
                ticker=self._metrics.profile.ticker,
                is_suitable=False,
                total_severity_score=self._score,
                interpretation=interpretation,
                factors=self._factors,
            )
        self._check_profitability()
        self._check_risk_and_stability()
        self._check_capex_spike()
        self._check_growth_stage()
        is_suitable, interpretation = self._interpret_score()
        return ValuationCheckResult(
            ticker=self._metrics.profile.ticker,
            is_suitable=is_suitable,
            total_severity_score=self._score,
            interpretation=interpretation,
            factors=self._factors,
        )


def evaluate_dcf(
    stock_metrics: StockMetrics,
    registry: Optional[MissingValueRegistry] = None,
) -> ValuationCheckResult:
    return DCFChecker(stock_metrics, registry).evaluate()
