from typing import List, Optional, Tuple

from config.config_loader import load_validator_config
from domain.core.enums import Sectors
from domain.metrics.stock import StockMetrics
from domain.valuation.policies import (
    CheckFactor,
    FactorSeverity,
    ValuationChecker,
    ValuationCheckResult,
)

_cfg = load_validator_config("dcf")


def _sector(stock_metrics: StockMetrics) -> Optional[Sectors]:
    return stock_metrics.profile.sector if stock_metrics.profile else None


class DCFChecker(ValuationChecker):

    CRITICAL_WEIGHT = 3
    WARNING_WEIGHT  = 1

    def __init__(self, stock_metrics: StockMetrics):
        self._metrics = stock_metrics
        self._factors: List[CheckFactor] = []
        self._score = 0

    def _add_factor(self, name, message, severity, value=None):
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
        if 1 <= score <= 5:
            return True,  "Minor warnings, generally suitable for DCF."
        if 6 <= score <= 10:
            return False, "Moderate concerns, use DCF with caution."
        return False, "Significant risk, DCF may be unreliable."

    def _check_free_cash_flow(self):
        sector = _sector(self._metrics)
        fcf_ttm          = self._metrics.cash_flow.fcf_ttm
        last_quarter_fcf = self._metrics.cash_flow.last_quarter_fcf
        last_year_fcf    = self._metrics.cash_flow.last_year_fcf

        fcf_negative_severity = (
            FactorSeverity.WARNING
            if sector == Sectors.REAL_ESTATE
            else FactorSeverity.CRITICAL
        )

        if fcf_ttm is None:
            self._add_factor(
                "Missing FCF (TTM)",
                "Free Cash Flow (TTM) data is missing.",
                FactorSeverity.CRITICAL,
            )
        elif fcf_ttm < 0:
            message = f"Free Cash Flow (TTM) is negative: {fcf_ttm:,.0f}"
            if last_quarter_fcf is not None and last_quarter_fcf > 0:
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

        if last_year_fcf is None:
            self._add_factor(
                "Missing Last Year FCF",
                "Last Year FCF data is missing.",
                FactorSeverity.CRITICAL,
            )
        elif last_year_fcf < 0:
            self._add_factor(
                "Negative Last Year FCF",
                f"Last Year FCF is negative: {last_year_fcf:,.0f}",
                fcf_negative_severity,
                last_year_fcf,
            )

    def _check_profitability(self):
        eps_ttm         = self._metrics.market_data.eps_ttm if self._metrics.market_data else None
        net_income_ttm  = self._metrics.financials.net_income_ttm
        operating_cf_ttm = self._metrics.cash_flow.operating_cf_ttm

        if eps_ttm is None or eps_ttm <= 0:
            self._add_factor(
                "Negative EPS (TTM)",
                f"Earnings Per Share (TTM) is zero, negative, or missing: {eps_ttm}",
                FactorSeverity.CRITICAL,
                eps_ttm,
            )

        if net_income_ttm is None:
            self._add_factor(
                "Missing Net Income (TTM)",
                "Net Income (TTM) data is missing.",
                FactorSeverity.CRITICAL,
            )
        elif net_income_ttm <= 0:
            self._add_factor(
                "Negative Net Income (TTM)",
                f"Net Income (TTM) is zero or negative: {net_income_ttm:,.0f}",
                FactorSeverity.CRITICAL,
                net_income_ttm,
            )

        if operating_cf_ttm is None:
            self._add_factor(
                "Missing Operating CF",
                "Operating Cash Flow (TTM) data is missing.",
                FactorSeverity.CRITICAL,
            )
        elif operating_cf_ttm < 0:
            self._add_factor(
                "Negative Operating CF",
                f"Operating Cash Flow (TTM) is negative: {operating_cf_ttm:,.0f}",
                FactorSeverity.CRITICAL,
                operating_cf_ttm,
            )

    def _check_risk_and_stability(self):
        sector     = _sector(self._metrics)
        market_data = self._metrics.market_data
        valuation  = self._metrics.valuation

        cost_of_debt  = valuation.cost_of_debt if valuation else None
        cod_threshold = _cfg.get_float("cost_of_debt_critical", sector, default=0.20)
        if cost_of_debt is not None and cost_of_debt > cod_threshold:
            self._add_factor(
                "High Cost of Debt",
                (
                    f"Cost of Debt ({cost_of_debt:.1%}) exceeds the sector threshold "
                    f"of {cod_threshold:.1%} for {sector.value if sector else 'unknown'}, "
                    "increasing WACC risk."
                ),
                FactorSeverity.CRITICAL,
                cost_of_debt,
            )

        tax_rate = valuation.corporate_tax_rate if valuation else None
        if tax_rate is not None and tax_rate < 0:
            self._add_factor(
                "Negative Tax Rate",
                f"Corporate Tax Rate is negative: {tax_rate:.2%}",
                FactorSeverity.WARNING,
                tax_rate,
            )

        beta           = market_data.beta if market_data else None
        beta_threshold = _cfg.get_float("beta_warning", sector, default=2.0)
        if beta is not None and beta > beta_threshold:
            self._add_factor(
                "High Beta",
                (
                    f"Stock Beta ({beta:.2f}) exceeds the sector threshold of "
                    f"{beta_threshold:.1f} for {sector.value if sector else 'unknown'}, "
                    "suggesting elevated volatility and forecast uncertainty."
                ),
                FactorSeverity.WARNING,
                beta,
            )

        market_cap    = market_data.market_cap if market_data else None
        cap_threshold = _cfg.get_int("market_cap_warning", sector, default=500_000_000)
        if market_cap is not None and market_cap < cap_threshold:
            self._add_factor(
                "Small Market Cap",
                (
                    f"Market cap (${market_cap:,.0f}) is below the sector threshold of "
                    f"${cap_threshold:,.0f} for {sector.value if sector else 'unknown'}, "
                    "which may reduce long-term forecast reliability."
                ),
                FactorSeverity.WARNING,
                market_cap,
            )

    def _check_growth_stage(self):
        revenue_growth_rate = self._metrics.financials.revenue_growth_rate
        net_income_ttm      = self._metrics.financials.net_income_ttm

        if (
            revenue_growth_rate is not None
            and revenue_growth_rate > 0.2
            and net_income_ttm is not None
            and net_income_ttm < 0
        ):
            self._add_factor(
                "Growth-Stage Startup",
                (
                    f"High revenue growth ({revenue_growth_rate * 100:.2f}%) with negative "
                    "net income indicates a potentially high-risk, high-growth startup phase."
                ),
                FactorSeverity.WARNING,
                revenue_growth_rate,
            )

    def evaluate(self) -> ValuationCheckResult:
        self._check_free_cash_flow()
        self._check_profitability()
        self._check_risk_and_stability()
        self._check_growth_stage()
        is_suitable, interpretation = self._interpret_score()
        return ValuationCheckResult(
            ticker=self._metrics.profile.ticker,
            is_suitable=is_suitable,
            total_severity_score=self._score,
            interpretation=interpretation,
            factors=self._factors,
        )


def evaluate_dcf(stock_metrics: StockMetrics) -> ValuationCheckResult:
    return DCFChecker(stock_metrics).evaluate()