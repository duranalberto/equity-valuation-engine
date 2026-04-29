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


class EVEBITDAChecker(ValuationChecker):
    """
    Suitability checker for EV/EBITDA relative valuation.

    Hard blocks:
    - EBITDA ≤ 0 (negative EBITDA makes the multiple meaningless)
    - Sector multiple unavailable

    Warnings:
    - Company EV/EBITDA > 2× sector median (already richly priced)
    - Debt-to-assets > 0.6
    - Negative net income alongside negative operating income (distress signal)
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

    def _missing_severity(self, model, field, default=FactorSeverity.CRITICAL):
        if self._registry is None:
            return default
        entry = self._registry.get(model, field)
        if entry and entry.reason == MissingReason.NOT_APPLICABLE:
            return FactorSeverity.WARNING
        return default

    def _interpret_score(self) -> Tuple[bool, str]:
        s = self._score
        if s == 0:   return True,  "Suitable for EV/EBITDA valuation."
        if s <= 2:   return True,  "Minor warnings — EV/EBITDA result should be reviewed carefully."
        if s <= 5:   return True,  "Moderate concerns — interpret EV/EBITDA cautiously."
        return False, "EV/EBITDA valuation blocked — significant data or structural issues."

    def _check_ebitda(self):
        ebitda = self._metrics.financials.ebitda_ttm
        if ebitda <= 0:
            if ebitda == 0.0 and self._registry and self._registry.has_missing_field("Financials", "ebitda_ttm"):
                sev = self._missing_severity("Financials", "ebitda_ttm")
                self._add_factor("Missing EBITDA", "EBITDA (TTM) is missing.", sev)
            else:
                self._add_factor(
                    "Negative/Zero EBITDA",
                    f"EBITDA (TTM) is {ebitda:,.0f} — EV/EBITDA multiple is undefined or negative. "
                    "Cannot perform relative valuation on a company with no operating earnings.",
                    FactorSeverity.CRITICAL,
                    ebitda,
                    weight_override=99,
                )

    def _check_sector_multiple(self):
        from .defaults import get_multiple

        base_multiple = get_multiple(self._metrics, "Base")
        if base_multiple is None:
            sector = self._metrics.profile.sector
            sector_label = sector.value if sector is not None else "unknown"
            self._add_factor(
                "Missing Sector EV/EBITDA Multiple",
                f"No configured Base EV/EBITDA multiple is available for sector "
                f"{sector_label!r}. EV/EBITDA valuation requires an explicit sector "
                "median and will not use a global default.",
                FactorSeverity.CRITICAL,
                weight_override=99,
            )

    def _check_relative_richness(self):
        """Warn when current EV/EBITDA is already above 2× the sector median."""
        val    = self._metrics.valuation
        fin    = self._metrics.financials
        ev     = val.enterprise_value if val else 0.0
        ebitda = fin.ebitda_ttm
        if ebitda <= 0 or ev <= 0:
            return
        current_multiple = ev / ebitda
        # Rough sector median: use the base multiple from config
        from .defaults import get_multiple
        base_multiple = get_multiple(self._metrics, "Base")
        if base_multiple is not None and base_multiple > 0 and current_multiple > 2 * base_multiple:
            self._add_factor(
                "Very High Current EV/EBITDA",
                f"Current EV/EBITDA ({current_multiple:.1f}×) is more than 2× the sector "
                f"median ({base_multiple:.1f}×). The stock may be richly priced relative "
                "to peers; sector multiple may understate intrinsic value.",
                FactorSeverity.WARNING,
                current_multiple,
            )

    def _check_operating_distress(self):
        fin = self._metrics.financials
        if fin.operating_income_ttm < 0 and fin.net_income_ttm < 0:
            self._add_factor(
                "Operating and Net Loss",
                f"Both operating income ({fin.operating_income_ttm:,.0f}) and net income "
                f"({fin.net_income_ttm:,.0f}) are negative — the company is loss-making at "
                "the operating level, which limits the interpretability of EV/EBITDA.",
                FactorSeverity.WARNING,
                fin.operating_income_ttm,
            )

    def _check_leverage(self):
        bs = self._metrics.balance_sheet
        if bs.total_assets <= 0:
            return
        debt_to_assets = bs.total_debt / bs.total_assets
        if debt_to_assets > 0.60:
            self._add_factor(
                "High Debt-to-Assets",
                f"Debt-to-assets is {debt_to_assets:.1%} — high leverage can distort "
                "enterprise-value multiples and increase equity risk.",
                FactorSeverity.WARNING,
                debt_to_assets,
            )

    def evaluate(self) -> ValuationCheckResult:
        self._check_ebitda()
        if self._score >= 99:
            _, interp = self._interpret_score()
            return ValuationCheckResult(
                ticker=self._metrics.profile.ticker,
                is_suitable=False,
                total_severity_score=self._score,
                interpretation="EV/EBITDA valuation blocked: EBITDA is zero or negative.",
                factors=self._factors,
            )
        self._check_sector_multiple()
        if self._score >= 99:
            return ValuationCheckResult(
                ticker=self._metrics.profile.ticker,
                is_suitable=False,
                total_severity_score=self._score,
                interpretation="EV/EBITDA valuation blocked: sector multiple is unavailable.",
                factors=self._factors,
            )
        self._check_relative_richness()
        self._check_leverage()
        self._check_operating_distress()
        is_suitable, interpretation = self._interpret_score()
        return ValuationCheckResult(
            ticker=self._metrics.profile.ticker,
            is_suitable=is_suitable,
            total_severity_score=self._score,
            interpretation=interpretation,
            factors=self._factors,
        )
