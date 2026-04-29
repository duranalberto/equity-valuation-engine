from typing import Optional

from domain.core.missing_registry import MissingValueRegistry
from domain.metrics.stock import StockMetrics
from domain.valuation.models.ps import PSParameters, PSValuationReport
from domain.valuation.policies import ValuationCheckResult
from domain.valuation.valuation_manager import ValuationManager

from .defaults import get_params
from .validator import PSChecker
from .valuation import execute_ps_scenarios


class PSManager(ValuationManager[PSValuationReport]):
    """Orchestrates P/S revenue multiple valuation."""

    def __init__(
        self,
        stock_metrics: StockMetrics,
        projection_years: int = 10,
        params: Optional[PSParameters] = None,
    ) -> None:
        self.report: Optional[PSValuationReport] = None
        self.set_valuation(stock_metrics, projection_years, params)

    def set_valuation(
        self,
        stock_metrics: StockMetrics,
        projection_years: int = 10,
        params: Optional[PSParameters] = None,
    ) -> None:
        self.stock_metrics = stock_metrics
        self.params = params if params is not None else get_params(stock_metrics, projection_years)
        self.params.projection_years = projection_years

    def execute_valuation_scenarios(self) -> PSValuationReport:
        self.report = execute_ps_scenarios(self.stock_metrics, self.params)
        return self.report

    def get_default_params(self) -> PSParameters:
        return get_params(self.stock_metrics, self.params.projection_years)

    def validate_metrics(
        self,
        registry: Optional[MissingValueRegistry] = None,
    ) -> ValuationCheckResult:
        return PSChecker(self.stock_metrics, registry).evaluate()
