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
# BUG-8 fix + DESIGN-2 fix: unified block threshold = 6 (was 7).
#
# Negative ROE produces a negative terminal income → negative required_value
# → negative intrinsic value → misleading "overvalued" signal.
# Weight set to 99 (hard-block sentinel) so the model never runs on
# negative ROE regardless of other factor scores.
# ---------------------------------------------------------------------------
_SCORE_BLOCK_THRESHOLD = 6
_NEGATIVE_ROE_WEIGHT   = 99


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
        elif 1 <= score <= 2:
            return True,  "Minor warnings, generally suitable for ROE-based models."
        elif 3 <= score <= 5:
            return True,  "Minor concerns, interpret ROE result carefully."
        elif score == _NEGATIVE_ROE_WEIGHT:
            return False, (
                "ROE valuation invalid: Return on Equity is negative. "
                "Negative ROE produces a negative terminal income and negative intrinsic "
                "value, which is meaningless as an equity valuation. "
                "Use DCF or P/E models instead."
            )
        else:
            return False, "Significant risk, ROE valuation is unreliable."

    def _check_shares_outstanding(self):
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

        # BUG-8 fix: negative ROE hard-blocks the model with weight=99.
        # Zero ROE is treated as missing (CRITICAL weight=3, may still block).
        if roe < 0:
            self._add_factor(
                "Negative ROE — Model Invalid",
                f"Return on Equity is {roe:.2%}. Negative ROE makes the ROE valuation "
                f"mathematically invalid: terminal income = ROE × equity_year_N < 0, "
                f"producing a negative intrinsic value. "
                f"Net income (TTM) = {financials.net_income_ttm:,.0f}. "
                f"Use DCF or P/E models for loss-making companies.",
                FactorSeverity.CRITICAL,
                roe,
                weight_override=_NEGATIVE_ROE_WEIGHT,
            )
            return  # no point adding further profitability sub-checks

        if roe == 0.0:
            sev = self._missing_severity("Ratios", "return_on_equity")
            self._add_factor(
                "Zero/Missing ROE",
                f"Return on Equity (ROE) is zero or missing: {roe}. "
                "ROE-based valuation may be unreliable.",
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
        ratios           = self._metrics.ratios
        return_on_assets = ratios.return_on_assets if ratios else 0.0
        if return_on_assets != 0.0 and return_on_assets < 0.05:
            self._add_factor(
                "Low Return on Assets (ROA)",
                f"ROA is low: {return_on_assets:.2%}. Indicates low asset efficiency.",
                FactorSeverity.WARNING,
                return_on_assets,
            )

    def _check_buyback_dominance(self):
        """
        BUG-13 fix: inform user when buybacks dominate over dividends so they
        understand the ROE model will use total shareholder yield (div + buyback)
        as the distribution component.
        """
        cf     = self._metrics.cash_flow
        ratios = self._metrics.ratios
        dividends = abs(cf.dividends_paid_ttm)
        buybacks  = abs(cf.share_buybacks_ttm)

        if buybacks > 0 and dividends == 0:
            bby = ratios.buyback_yield if ratios else 0.0
            self._add_factor(
                "Buyback-Only Capital Return",
                f"Company pays no dividends but repurchased {buybacks/1e9:.1f}B TTM "
                f"(buyback yield {bby:.2%}). The ROE model will include buyback yield "
                f"({bby:.2%}) as the per-share distribution component in place of dividends. "
                f"This improves accuracy for capital-return companies.",
                FactorSeverity.INFO,
                buybacks,
                weight_override=0,
            )
        elif buybacks > 2 * dividends and dividends > 0:
            tsy = ratios.total_shareholder_yield if ratios else 0.0
            self._add_factor(
                "Buybacks Dominate Dividends",
                f"Share buybacks ({buybacks/1e9:.1f}B) are more than 2× dividends "
                f"({dividends/1e9:.1f}B). Total shareholder yield used: {tsy:.2%}.",
                FactorSeverity.INFO,
                buybacks,
                weight_override=0,
            )

    def evaluate(self) -> ValuationCheckResult:
        self._check_shares_outstanding()
        self._check_profitability_and_return()
        # Short-circuit: if the hard-block sentinel was triggered (negative ROE)
        # all further checks are irrelevant — the model is unconditionally invalid.
        if self._score >= _NEGATIVE_ROE_WEIGHT:
            return ValuationCheckResult(
                ticker=self._metrics.profile.ticker,
                is_suitable=False,
                total_severity_score=self._score,
                interpretation=(
                    "ROE valuation invalid: Return on Equity is negative. "
                    "Negative ROE produces a negative terminal income and negative intrinsic "
                    "value, which is meaningless as an equity valuation. "
                    "Use DCF or P/E models instead."
                ),
                factors=self._factors,
            )
        self._check_leverage()
        self._check_asset_quality()
        self._check_buyback_dominance()
        is_suitable, interpretation = self._interpret_score()
        return ValuationCheckResult(
            ticker=self._metrics.profile.ticker,
            is_suitable=is_suitable,
            total_severity_score=self._score,
            interpretation=interpretation,
            factors=self._factors,
        )