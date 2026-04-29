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


class DDMChecker(ValuationChecker):
    """
    Suitability checker for the Gordon Growth DDM.

    Hard blocks:
    - dividends_paid_ttm = 0 (no dividends to discount)
    - payout_ratio > 1.0 (unsustainable — company paying out more than it earns)
    - required_return ≤ terminal_growth_rate (Gordon Growth formula undefined)

    Warnings:
    - Dividend growth exceeds revenue growth
    - Interest coverage below 2.0
    - High payout ratio (> 80%) — leaves little room for future growth
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
        if s == 0:  return True,  "Suitable for DDM valuation."
        if s <= 2:  return True,  "Minor warnings — DDM result should be reviewed."
        if s <= 5:  return True,  "Moderate concerns — interpret DDM cautiously."
        return False, "DDM valuation blocked — dividends absent, unsustainable, or model undefined."

    def _check_dividends(self):
        divs = abs(self._metrics.cash_flow.dividends_paid_ttm)
        if divs == 0:
            self._add_factor(
                "No Dividends Paid",
                "dividends_paid_ttm is zero — DDM requires a positive dividend stream. "
                "Use DCF or ROE models for non-dividend-paying companies.",
                FactorSeverity.CRITICAL, 0.0, weight_override=99,
            )
            return

        ratios = self._metrics.ratios
        payout = ratios.payout_ratio if ratios else 0.0
        if payout > 1.0:
            self._add_factor(
                "Unsustainable Payout Ratio",
                f"Payout ratio is {payout:.0%} — company is distributing more than it earns. "
                "Dividend is likely unsustainable; DDM intrinsic value will be unreliable.",
                FactorSeverity.CRITICAL, payout, weight_override=99,
            )
        elif payout > 0.80:
            self._add_factor(
                "High Payout Ratio",
                f"Payout ratio is {payout:.0%} — little retained earnings for future growth. "
                "DDM terminal growth rate assumptions may be optimistic.",
                FactorSeverity.WARNING, payout,
            )

    def _check_gordon_growth_feasibility(self):
        """Required return must strictly exceed terminal growth rate."""
        from .defaults import get_params
        params = get_params(self._metrics)
        from calculations.dfc_formulas import cost_of_equity_capm
        beta = self._metrics.market_data.beta or 1.0
        required_return = cost_of_equity_capm(
            params.risk_free_rate, beta, params.market_risk_premium
        )
        if required_return <= params.terminal_growth_rate:
            self._add_factor(
                "Gordon Growth Undefined",
                f"Required return ({required_return:.2%}) ≤ terminal growth rate "
                f"({params.terminal_growth_rate:.2%}). Gordon Growth formula (D1/(r−g)) "
                "is undefined when r ≤ g.",
                FactorSeverity.CRITICAL, required_return, weight_override=99,
            )

    def _check_dividend_growth_quality(self):
        from .valuation import _dividend_growth_rate
        dividend_growth = _dividend_growth_rate(self._metrics)
        revenue_growth = self._metrics.financials.revenue_growth_rate
        if dividend_growth > revenue_growth:
            self._add_factor(
                "Dividend Growth Exceeds Revenue Growth",
                f"Dividend growth ({dividend_growth:.1%}) exceeds revenue growth "
                f"({revenue_growth:.1%}). Dividend assumptions may outrun the business.",
                FactorSeverity.WARNING,
                dividend_growth,
            )

    def _check_interest_coverage(self):
        ratios = self._metrics.ratios
        if ratios is None:
            return
        has_debt_cost = (
            self._metrics.balance_sheet.total_debt > 0
            or self._metrics.financials.interest_expense_ttm != 0
        )
        if has_debt_cost and ratios.interest_coverage < 2.0:
            self._add_factor(
                "Low Interest Coverage",
                f"Interest coverage is {ratios.interest_coverage:.2f}x — weak debt "
                "service capacity raises dividend sustainability risk.",
                FactorSeverity.WARNING,
                ratios.interest_coverage,
            )

    def evaluate(self) -> ValuationCheckResult:
        self._check_dividends()
        if self._score >= 99:
            return ValuationCheckResult(
                ticker=self._metrics.profile.ticker,
                is_suitable=False,
                total_severity_score=self._score,
                interpretation=self._interpret_score()[1],
                factors=self._factors,
            )
        self._check_gordon_growth_feasibility()
        if self._score >= 99:
            return ValuationCheckResult(
                ticker=self._metrics.profile.ticker,
                is_suitable=False,
                total_severity_score=self._score,
                interpretation=self._interpret_score()[1],
                factors=self._factors,
            )
        self._check_dividend_growth_quality()
        self._check_interest_coverage()
        is_suitable, interpretation = self._interpret_score()
        return ValuationCheckResult(
            ticker=self._metrics.profile.ticker,
            is_suitable=is_suitable,
            total_severity_score=self._score,
            interpretation=interpretation,
            factors=self._factors,
        )
