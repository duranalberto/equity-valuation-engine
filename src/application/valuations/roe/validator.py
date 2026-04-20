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


class ROEChecker(ValuationChecker):

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
            return True,  "Highly suitable for ROE-based valuation."
        elif 1 <= score <= 3:
            return True,  "Minor warnings, generally suitable for ROE-based models."
        elif 4 <= score <= 7:
            return False, "Moderate concerns, ROE may be distorted or unsustainable."
        else:
            return False, "Significant risk, ROE valuation is unreliable."

    def _check_shares_outstanding(self):
        """
        Verify shares_outstanding is present and positive.

        ``execute_roe_scenarios`` calls ``safe_div(dividends, shares)`` which
        returns ``None`` when shares is zero, then raises ``ValueError``.
        """
        market_data = self._metrics.market_data
        shares = market_data.shares_outstanding if market_data else 0
        if shares <= 0:
            self._add_factor(
                "Missing/Zero Shares Outstanding",
                f"Shares outstanding is missing or non-positive: {shares}. "
                "Cannot compute dividend rate per share for ROE valuation.",
                FactorSeverity.CRITICAL,
                shares,
            )

    def _check_profitability_and_return(self):
        ratios        = self._metrics.ratios
        balance_sheet = self._metrics.balance_sheet
        financials    = self._metrics.financials
        roe           = ratios.return_on_equity if ratios else 0.0
        total_equity  = balance_sheet.total_equity

        if roe <= 0:
            sev = self._missing_severity("Ratios", "return_on_equity") \
                if roe == 0.0 else FactorSeverity.CRITICAL
            self._add_factor(
                "Non-Positive ROE",
                f"Return on Equity (ROE) is zero, negative, or missing: {roe}. "
                "ROE-based valuation is invalid.",
                sev,
                roe,
            )

        if total_equity <= 0:
            sev = self._missing_severity("BalanceSheet", "total_equity") \
                if total_equity == 0.0 else FactorSeverity.CRITICAL
            self._add_factor(
                "Negative/Missing Equity",
                f"Total Shareholder Equity is non-positive: {total_equity}. "
                "ROE is mathematically meaningless.",
                sev,
                total_equity,
            )

        if financials.net_margin != 0.0 and financials.net_margin < 0.05:
            self._add_factor(
                "Low Net Margin",
                f"Net Margin is low: {financials.net_margin:.2%}. "
                "Sustainable high ROE is difficult with thin margins.",
                FactorSeverity.WARNING,
                financials.net_margin,
            )

    def _check_leverage(self):
        ratios         = self._metrics.ratios
        debt_to_equity = ratios.debt_to_equity if ratios else 0.0
        if debt_to_equity > 1.5:
            self._add_factor(
                "High Financial Leverage",
                f"Debt-to-Equity ratio is high: {debt_to_equity:.2f}. "
                "Current ROE may be unsustainably boosted by debt.",
                FactorSeverity.WARNING,
                debt_to_equity,
            )

    def _check_asset_quality(self):
        ratios              = self._metrics.ratios
        return_on_assets    = ratios.return_on_assets if ratios else 0.0
        # Only flag when ROA is genuinely low (non-zero but below threshold);
        # 0.0 is handled by the registry / profitability check above.
        if return_on_assets != 0.0 and return_on_assets < 0.05:
            self._add_factor(
                "Low Return on Assets (ROA)",
                f"ROA is low: {return_on_assets:.2%}. Indicates low asset efficiency.",
                FactorSeverity.WARNING,
                return_on_assets,
            )

    def evaluate(self) -> ValuationCheckResult:
        self._check_shares_outstanding()
        self._check_profitability_and_return()
        self._check_leverage()
        self._check_asset_quality()
        is_suitable, interpretation = self._interpret_score()
        return ValuationCheckResult(
            ticker=self._metrics.profile.ticker,
            is_suitable=is_suitable,
            total_severity_score=self._score,
            interpretation=interpretation,
            factors=self._factors,
        )
