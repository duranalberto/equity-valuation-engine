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

_SCORE_BLOCK_THRESHOLD = 6


class PSChecker(ValuationChecker):
    """
    Suitability checker for P/S revenue multiple valuation.

    Hard blocks:
    - Revenue ≤ 0
    - Declining revenue (revenue_growth_rate < 0) — P/S unreliable for shrinking businesses
    - Gross margin below 20%
    - Sector multiple unavailable

    Warnings:
    - Very high current P/S vs sector median (richly priced)
    - Company is deeply unprofitable at the operating level
    """

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
        weight = weight_override if weight_override is not None else (
            self.CRITICAL_WEIGHT if severity == FactorSeverity.CRITICAL
            else self.WARNING_WEIGHT if severity == FactorSeverity.WARNING
            else 0
        )
        self._factors.append(
            CheckFactor(name=name, message=message, severity=severity, weight=weight, value=value)
        )
        self._score += weight

    def _interpret_score(self) -> Tuple[bool, str]:
        s = self._score
        if s == 0:  return True,  "Suitable for P/S valuation."
        if s <= 2:  return True,  "Minor warnings — P/S result should be cross-checked."
        if s <= 5:  return True,  "Moderate concerns — interpret P/S with caution."
        return False, "P/S valuation blocked — revenue is zero, declining, or sector data missing."

    def _check_revenue(self):
        rev = self._metrics.financials.revenue_ttm
        if rev <= 0:
            if rev == 0.0 and self._registry and self._registry.has_missing_field("Financials", "revenue_ttm"):
                self._add_factor("Missing Revenue", "Revenue (TTM) data is missing.", FactorSeverity.CRITICAL)
            else:
                self._add_factor(
                    "Zero/Negative Revenue",
                    f"Revenue (TTM) is {rev:,.0f} — P/S multiple is undefined.",
                    FactorSeverity.CRITICAL, rev, weight_override=99,
                )

    def _check_revenue_growth(self):
        rgr = self._metrics.financials.revenue_growth_rate
        if rgr < 0:
            self._add_factor(
                "Declining Revenue",
                f"Revenue growth rate is {rgr:.1%} — P/S multiple is unreliable for "
                "companies with shrinking top lines.",
                FactorSeverity.CRITICAL, rgr, weight_override=99,
            )

    def _check_sector_multiple(self):
        from .defaults import get_multiple

        base_multiple = get_multiple(self._metrics, "Base")
        if base_multiple is None:
            sector = self._metrics.profile.sector
            sector_label = sector.value if sector is not None else "unknown"
            self._add_factor(
                "Missing Sector P/S Multiple",
                f"No configured Base P/S multiple is available for sector "
                f"{sector_label!r}. P/S valuation requires an explicit sector "
                "median and will not use a global default.",
                FactorSeverity.CRITICAL,
                weight_override=99,
            )

    def _check_profitability_context(self):
        fin = self._metrics.financials
        if fin.gross_margin < 0.20:
            self._add_factor(
                "Low Gross Margin",
                f"Gross margin is {fin.gross_margin:.1%}, below the 20.0% minimum "
                "for P/S valuation. Revenue has too little conversion into gross "
                "profit for a sales multiple to be analytically reliable.",
                FactorSeverity.CRITICAL, fin.gross_margin, weight_override=99,
            )
        if fin.operating_margin < -0.20:
            self._add_factor(
                "Deeply Negative Operating Margin",
                f"Operating margin is {fin.operating_margin:.1%} — very high cash burn "
                "relative to revenue. P/S output should be interpreted as optimistic.",
                FactorSeverity.WARNING, fin.operating_margin,
            )

    def _check_relative_richness(self):
        val = self._metrics.valuation
        ratios = self._metrics.ratios
        current_ps = 0.0
        if val and val.price_to_sales > 0:
            current_ps = val.price_to_sales
        elif ratios and ratios.price_to_sales > 0:
            current_ps = ratios.price_to_sales

        if current_ps <= 0:
            return

        from .defaults import get_multiple
        base_multiple = get_multiple(self._metrics, "Base")
        if base_multiple is not None and base_multiple > 0 and current_ps > 3 * base_multiple:
            self._add_factor(
                "Very High Current P/S",
                f"Current P/S ({current_ps:.1f}x) is more than 3x the sector median "
                f"({base_multiple:.1f}x). Revenue multiple output should be treated "
                "as highly sensitive to peer-multiple compression.",
                FactorSeverity.WARNING,
                current_ps,
            )

    def evaluate(self) -> ValuationCheckResult:
        self._check_revenue()
        if self._score >= 99:
            return ValuationCheckResult(
                ticker=self._metrics.profile.ticker,
                is_suitable=False,
                total_severity_score=self._score,
                interpretation="P/S valuation blocked: revenue is zero or negative.",
                factors=self._factors,
            )
        self._check_revenue_growth()
        if self._score >= 99:
            return ValuationCheckResult(
                ticker=self._metrics.profile.ticker,
                is_suitable=False,
                total_severity_score=self._score,
                interpretation="P/S valuation blocked: revenue is declining.",
                factors=self._factors,
            )
        self._check_sector_multiple()
        if self._score >= 99:
            return ValuationCheckResult(
                ticker=self._metrics.profile.ticker,
                is_suitable=False,
                total_severity_score=self._score,
                interpretation="P/S valuation blocked: sector multiple is unavailable.",
                factors=self._factors,
            )
        self._check_profitability_context()
        if self._score >= 99:
            return ValuationCheckResult(
                ticker=self._metrics.profile.ticker,
                is_suitable=False,
                total_severity_score=self._score,
                interpretation="P/S valuation blocked: gross margin is below 20%.",
                factors=self._factors,
            )
        self._check_relative_richness()
        is_suitable, interpretation = self._interpret_score()
        return ValuationCheckResult(
            ticker=self._metrics.profile.ticker,
            is_suitable=is_suitable,
            total_severity_score=self._score,
            interpretation=interpretation,
            factors=self._factors,
        )
