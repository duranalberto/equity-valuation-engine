from typing import Optional

from domain.core.missing_registry import MissingValueRegistry
from domain.metrics.stock import StockMetrics
from domain.valuation.models.nav import NAVParameters, NAVValuationReport
from domain.valuation.policies import ValuationCheckResult
from domain.valuation.valuation_manager import ValuationManager

from .defaults import get_params
from .validator import NAVChecker
from .valuation import execute_nav_scenarios


class NAVManager(ValuationManager[NAVValuationReport]):
    """Orchestrates NAV (Asset-Based) valuation."""

    def __init__(
        self,
        stock_metrics: StockMetrics,
        projection_years: int = 10,
        params: Optional[NAVParameters] = None,
    ) -> None:
        self.report: Optional[NAVValuationReport] = None
        self.set_valuation(stock_metrics, projection_years, params)

    def set_valuation(
        self,
        stock_metrics: StockMetrics,
        projection_years: int = 10,
        params: Optional[NAVParameters] = None,
    ) -> None:
        self.stock_metrics = stock_metrics
        self.params = params if params is not None else get_params(stock_metrics, projection_years)
        self.params.projection_years = projection_years

    def execute_valuation_scenarios(self) -> NAVValuationReport:
        self.report = execute_nav_scenarios(self.stock_metrics, self.params)
        return self.report

    def get_default_params(self) -> NAVParameters:
        return get_params(self.stock_metrics, self.params.projection_years)

    def validate_metrics(
        self,
        registry: Optional[MissingValueRegistry] = None,
    ) -> ValuationCheckResult:
        return NAVChecker(self.stock_metrics, registry).evaluate()
