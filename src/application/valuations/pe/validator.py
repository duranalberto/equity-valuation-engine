from typing import List, Optional, Tuple

from domain.core.missing import MissingReason
from domain.core.missing_registry import MissingValueRegistry
from domain.metrics.stock import StockMetrics
from domain.valuation.policies import (
    CheckFactor,
    FactorSeverity,
    ValuationChecker,
    ValuationCheckResult,
)

# ---------------------------------------------------------------------------
# BUG-9 fix + DESIGN-2 fix: unified block threshold = 6 (was 7).
# pe_ttm is now Optional[float]; every comparison guarded against None.
# ---------------------------------------------------------------------------
_SCORE_BLOCK_THRESHOLD = 6


class PEChecker(ValuationChecker):

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

    def _interpret_score(self) -> Tuple[bool, str]:
        score = self._score
        if score == 0:
            return True,  "Perfectly suitable for P/E valuation (requires positive EPS)."
        elif 1 <= score <= 2:
            return True,  "Minor warnings, generally suitable for P/E."
        elif 3 <= score <= 5:
            return True,  "Minor concerns, interpret P/E result carefully."
        else:
            return False, "Significant risk, P/E valuation is unreliable or invalid."

    def _check_valuation_inputs(self):
        """
        Firewall: block if median_historical_pe is None.
        pe_ttm is Optional[float] — guard all comparisons (BUG-9 fix).
        """
        median_pe = self._metrics.valuation.median_historical_pe
        if median_pe is None:
            detail = "Cannot execute P/E valuation without a historical P/E multiple."
            if self._registry is not None:
                entry = self._registry.get("Valuation", "median_historical_pe")
                if entry and entry.detail:
                    detail = entry.detail
            self._add_factor(
                "Missing Median Historical P/E",
                detail,
                FactorSeverity.CRITICAL,
            )

    def _check_earnings_stability(self):
        market_data = self._metrics.market_data
        eps_ttm = market_data.eps_ttm if market_data else 0.0
        # BUG-9 fix: pe_ttm is Optional[float]; never compare None to int/float
        pe_ttm  = market_data.pe_ttm  if market_data else None

        if eps_ttm <= 0:
            sev = self._missing_severity("MarketData", "eps_ttm") \
                if eps_ttm == 0.0 else FactorSeverity.CRITICAL
            self._add_factor(
                "Negative/Missing EPS (TTM)",
                f"EPS (TTM) is negative or missing: {eps_ttm}. P/E valuation is invalid.",
                sev,
                eps_ttm,
            )

        # Guard: only evaluate pe_ttm when it is a real number
        if pe_ttm is None:
            self._add_factor(
                "Missing P/E (TTM)",
                "P/E (TTM) ratio is unavailable (likely due to negative EPS). Cannot perform P/E valuation.",
                FactorSeverity.CRITICAL,
            )
        elif pe_ttm == 0.0:
            sev = self._missing_severity("MarketData", "pe_ttm")
            self._add_factor(
                "Missing P/E (TTM)",
                "P/E (TTM) ratio is zero or missing, cannot perform valuation.",
                sev,
            )
        elif pe_ttm > 40:
            self._add_factor(
                "Very High P/E",
                f"P/E (TTM) is high: {pe_ttm:.1f}, indicating high market expectations.",
                FactorSeverity.WARNING,
                pe_ttm,
            )

    def _check_growth_metrics(self):
        financials        = self._metrics.financials
        ratios            = self._metrics.ratios
        net_income_growth = financials.net_income_growth

        if net_income_growth <= 0:
            self._add_factor(
                "Non-Positive Growth",
                f"Net Income Growth is zero or negative: {net_income_growth}. "
                "Growth-based P/E assumptions are compromised.",
                FactorSeverity.WARNING,
                net_income_growth,
            )

        peg_ratio = ratios.peg_ratio if ratios else 0.0
        if peg_ratio < 0:
            self._add_factor(
                "Negative PEG Ratio",
                f"PEG Ratio is negative: {peg_ratio:.2f}. Indicates negative earnings growth.",
                FactorSeverity.CRITICAL,
                peg_ratio,
            )
        elif peg_ratio > 2.0:
            self._add_factor(
                "High PEG Ratio",
                f"PEG Ratio is high: {peg_ratio:.2f}. May indicate significant overvaluation.",
                FactorSeverity.WARNING,
                peg_ratio,
            )

    def _check_balance_sheet(self):
        ratios         = self._metrics.ratios
        debt_to_equity = ratios.debt_to_equity if ratios else 0.0
        if debt_to_equity > 2.0:
            self._add_factor(
                "High Debt-to-Equity",
                f"Debt-to-Equity ratio is high: {debt_to_equity:.2f}. "
                "High leverage increases risk to future EPS.",
                FactorSeverity.WARNING,
                debt_to_equity,
            )

    def evaluate(self) -> ValuationCheckResult:
        self._check_valuation_inputs()
        self._check_earnings_stability()
        self._check_growth_metrics()
        self._check_balance_sheet()
        is_suitable, interpretation = self._interpret_score()
        return ValuationCheckResult(
            ticker=self._metrics.profile.ticker,
            is_suitable=is_suitable,
            total_severity_score=self._score,
            interpretation=interpretation,
            factors=self._factors,
        )