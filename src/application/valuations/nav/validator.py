from typing import List, Optional, Tuple

from domain.core.missing_registry import MissingValueRegistry
from domain.metrics.stock import StockMetrics
from domain.valuation.policies import (
    CheckFactor,
    FactorSeverity,
    ValuationChecker,
    ValuationCheckResult,
)
from .defaults import get_intangible_cap

class NAVChecker(ValuationChecker):
    """
    Suitability checker for NAV (Asset-Based) valuation.

    Hard blocks:
    - total_assets = 0

    Warnings:
    - Negative book equity
    - Negative or zero NAV
    - Goodwill and intangibles exceed configured asset ratio threshold
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
        if s == 0:  return True,  "Suitable for NAV valuation."
        if s <= 2:  return True,  "Minor warnings — NAV result should be reviewed."
        if s <= 5:  return True,  "Moderate concerns — interpret NAV with caution."
        return False, "NAV valuation blocked — total assets zero or data unavailable."

    def _check_total_assets(self):
        ta = self._metrics.balance_sheet.total_assets
        if ta <= 0:
            self._add_factor(
                "Zero/Missing Total Assets",
                "total_assets is zero or missing — cannot perform asset-based valuation.",
                FactorSeverity.CRITICAL, ta, weight_override=99,
            )

    def _check_book_equity(self):
        """Warn on negative book equity without implying unavailable intangible data."""
        bs  = self._metrics.balance_sheet
        if bs.total_assets <= 0:
            return
        if bs.total_equity < 0:
            self._add_factor(
                "Negative Book Equity",
                f"total_equity is {bs.total_equity:,.0f}. Asset-based NAV should be "
                "reviewed carefully because book equity is already negative.",
                FactorSeverity.WARNING,
                bs.total_equity,
            )

    def _check_negative_nav(self):
        bs = self._metrics.balance_sheet
        if bs.total_liabilities >= bs.total_assets and bs.total_assets > 0:
            nav = bs.total_assets - bs.total_liabilities
            self._add_factor(
                "Negative/Zero NAV",
                f"total_liabilities ({bs.total_liabilities:,.0f}) ≥ total_assets "
                f"({bs.total_assets:,.0f}). Computed NAV = {nav:,.0f} which is ≤ 0. "
                "NAV intrinsic value will be negative or zero — not meaningful for equity.",
                FactorSeverity.WARNING, nav,
            )

    def _check_intangible_quality(self):
        bs = self._metrics.balance_sheet
        if bs.total_assets <= 0:
            return

        goodwill_and_intangibles = getattr(bs, "goodwill_and_intangibles", 0.0) or 0.0
        intangible_ratio = goodwill_and_intangibles / bs.total_assets
        intangible_cap = get_intangible_cap(self._metrics)
        if intangible_ratio > intangible_cap:
            self._add_factor(
                "High Goodwill/Intangibles",
                f"Goodwill and intangible assets are {intangible_ratio:.1%} of "
                f"total assets, above the configured {intangible_cap:.1%} cap. "
                "NAV depends heavily on soft assets and should be treated cautiously.",
                FactorSeverity.WARNING,
                intangible_ratio,
            )

    def evaluate(self) -> ValuationCheckResult:
        self._check_total_assets()
        if self._score >= 99:
            return ValuationCheckResult(
                ticker=self._metrics.profile.ticker,
                is_suitable=False,
                total_severity_score=self._score,
                interpretation="NAV valuation blocked: total assets is zero or missing.",
                factors=self._factors,
            )
        self._check_book_equity()
        self._check_negative_nav()
        self._check_intangible_quality()
        is_suitable, interpretation = self._interpret_score()
        return ValuationCheckResult(
            ticker=self._metrics.profile.ticker,
            is_suitable=is_suitable,
            total_severity_score=self._score,
            interpretation=interpretation,
            factors=self._factors,
        )
