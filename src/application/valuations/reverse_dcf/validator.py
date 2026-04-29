from typing import List, Optional, Tuple

from domain.core.missing_registry import MissingValueRegistry
from domain.metrics.stock import StockMetrics
from domain.valuation.policies import (
    CheckFactor,
    FactorSeverity,
    ValuationChecker,
    ValuationCheckResult,
)


class ReverseDCFChecker(ValuationChecker):
    """
    Suitability checker for Reverse DCF (implied growth back-solver).

    Hard blocks:
    - FCF ≤ 0 AND normalized_fcf is None (cannot back-solve from a negative FCF base)
    - current_price ≤ 0

    Warnings:
    - FCF spike detected (solver will use normalized_fcf)
    - Implied growth above 40%
    - Implied growth below 0%
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
        if s == 0:  return True,  "Suitable for Reverse DCF analysis."
        if s <= 2:  return True,  "Minor warnings — review implied growth rate carefully."
        if s <= 5:  return True,  "Moderate concerns — interpret Reverse DCF with caution."
        return False, "Reverse DCF blocked — negative FCF with no normalised alternative."

    def _check_fcf(self):
        val = self._metrics.valuation
        cf  = self._metrics.cash_flow
        fcf = cf.fcf_ttm
        normalised = val.normalized_fcf if val else None

        if fcf <= 0 and (normalised is None or normalised <= 0):
            self._add_factor(
                "Negative FCF — Back-Solve Impossible",
                f"FCF (TTM) is {fcf:,.0f} and no positive normalised FCF is available. "
                "Reverse DCF cannot back-solve for an implied growth rate from a negative FCF seed.",
                FactorSeverity.CRITICAL, fcf, weight_override=99,
            )
        elif fcf <= 0 and normalised and normalised > 0:
            self._add_factor(
                "Negative Raw FCF — Using Normalised Seed",
                f"Raw FCF (TTM) = {fcf:,.0f}. Reverse DCF will use normalised FCF "
                f"({normalised/1e9:.1f}B) due to capex spike. "
                "Implied growth rate reflects normalised base.",
                FactorSeverity.WARNING, fcf,
            )

    def _check_price(self):
        price = self._metrics.market_data.current_price
        if price <= 0:
            self._add_factor(
                "Invalid Market Price",
                f"current_price ({price}) must be positive for Reverse DCF.",
                FactorSeverity.CRITICAL, price, weight_override=99,
            )

    def _check_implied_growth(self):
        try:
            from .valuation import solve_reverse_dcf
            report = solve_reverse_dcf(self._metrics)
        except Exception as exc:
            self._add_factor(
                "Reverse DCF Solver Failed",
                f"Reverse DCF solver failed after input prechecks: {exc}",
                FactorSeverity.CRITICAL,
                weight_override=99,
            )
            return

        implied_growth = report.result.implied_growth_rate
        if implied_growth > 0.40:
            self._add_factor(
                "Very High Implied Growth",
                f"Reverse DCF implies {implied_growth:.1%} annual FCF growth, above "
                "the 40% warning threshold.",
                FactorSeverity.WARNING,
                implied_growth,
            )
        elif implied_growth < 0.0:
            self._add_factor(
                "Negative Implied Growth",
                f"Reverse DCF implies {implied_growth:.1%} annual FCF growth. The "
                "market price embeds shrinking free cash flow.",
                FactorSeverity.WARNING,
                implied_growth,
            )

    def evaluate(self) -> ValuationCheckResult:
        self._check_fcf()
        self._check_price()
        if self._score >= 99:
            return ValuationCheckResult(
                ticker=self._metrics.profile.ticker,
                is_suitable=False,
                total_severity_score=self._score,
                interpretation=self._interpret_score()[1],
                factors=self._factors,
            )
        self._check_implied_growth()
        is_suitable, interpretation = self._interpret_score()
        return ValuationCheckResult(
            ticker=self._metrics.profile.ticker,
            is_suitable=is_suitable,
            total_severity_score=self._score,
            interpretation=interpretation,
            factors=self._factors,
        )
