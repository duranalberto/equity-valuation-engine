from domain.metrics.stock import StockMetrics
from typing import List, Tuple, Union, Optional
from domain.valuation.policies import (
    ValuationChecker, CheckFactor, FactorSeverity, ValuationCheckResult,
)


class PEChecker(ValuationChecker):

    CRITICAL_WEIGHT = 3
    WARNING_WEIGHT = 1

    def __init__(self, stock_metrics: StockMetrics):
        self._metrics = stock_metrics
        self._factors: List[CheckFactor] = []
        self._score = 0

    def _add_factor(
        self,
        name: str,
        message: str,
        severity: FactorSeverity,
        value: Optional[Union[float, int]] = None,
    ):
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
            return True, "Perfectly suitable for P/E valuation (requires positive EPS)."
        elif 1 <= score <= 3:
            return True, "Minor warnings, generally suitable for P/E."
        elif 4 <= score <= 7:
            return False, "Moderate concerns, P/E ratio may be distorted."
        else:
            return False, "Significant risk, P/E valuation is unreliable or invalid."

    def _check_earnings_stability(self):
        market_data = self._metrics.market_data
        eps_ttm = market_data.eps_ttm if market_data else None
        pe_ttm = market_data.pe_ttm if market_data else None

        if eps_ttm is None or eps_ttm <= 0:
            self._add_factor(
                "Negative/Missing EPS (TTM)",
                f"EPS (TTM) is negative or missing: {eps_ttm}. P/E valuation is invalid.",
                FactorSeverity.CRITICAL,
                eps_ttm,
            )

        if pe_ttm is None:
            self._add_factor(
                "Missing P/E (TTM)",
                "P/E (TTM) ratio is missing, cannot perform valuation.",
                FactorSeverity.CRITICAL,
            )

        if pe_ttm is not None and pe_ttm > 40:
            self._add_factor(
                "Very High P/E",
                f"P/E (TTM) is high: {pe_ttm:.1f}, indicating high market expectations.",
                FactorSeverity.WARNING,
                pe_ttm,
            )

    def _check_growth_metrics(self):
        financials = self._metrics.financials
        ratios = self._metrics.ratios

        net_income_growth = financials.net_income_growth

        if net_income_growth is None or net_income_growth <= 0:
            self._add_factor(
                "Non-Positive Growth",
                f"Net Income Growth is zero or negative: {net_income_growth}. "
                "Growth-based P/E assumptions are compromised.",
                FactorSeverity.WARNING,
                net_income_growth,
            )

        peg_ratio = ratios.peg_ratio if ratios else None
        if peg_ratio is not None and peg_ratio < 0:
            self._add_factor(
                "Negative PEG Ratio",
                f"PEG Ratio is negative: {peg_ratio:.2f}. Indicates negative earnings growth.",
                FactorSeverity.CRITICAL,
                peg_ratio,
            )
        elif peg_ratio is not None and peg_ratio > 2.0:
            self._add_factor(
                "High PEG Ratio",
                f"PEG Ratio is high: {peg_ratio:.2f}. May indicate significant overvaluation.",
                FactorSeverity.WARNING,
                peg_ratio,
            )

    def _check_balance_sheet(self):
        ratios = self._metrics.ratios
        debt_to_equity = ratios.debt_to_equity if ratios else None

        if debt_to_equity is not None and debt_to_equity > 2.0:
            self._add_factor(
                "High Debt-to-Equity",
                f"Debt-to-Equity ratio is high: {debt_to_equity:.2f}. "
                "High leverage increases risk to future EPS.",
                FactorSeverity.WARNING,
                debt_to_equity,
            )

    def evaluate(self) -> ValuationCheckResult:
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