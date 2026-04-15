from typing import Optional

from domain.metrics.stock import StockMetrics
from domain.valuation.base import ValuationParams
from domain.valuation.models.roe import ROEParameters, ROEValuationReport
from domain.valuation.policies import ValuationCheckResult
from domain.valuation.valuation_manager import ValuationManager

from .defaults import get_params
from .validator import ROEChecker
from .valuation import execute_roe_scenarios


class ROEManager(ValuationManager[ROEValuationReport]):
    """
    Orchestrates ROE valuation: parameter resolution, scenario execution,
    and pre-flight suitability checking.
    """

    stock_metrics: StockMetrics
    params: ROEParameters

    def __init__(
        self,
        stock_metrics: StockMetrics,
        projection_years: int = 10,
        params: Optional[ValuationParams] = None,
    ) -> None:
        self.report: Optional[ROEValuationReport] = None
        self.set_valuation(stock_metrics, projection_years, params)

    def set_valuation(
        self,
        stock_metrics: StockMetrics,
        projection_years: int = 10,
        params: Optional[ValuationParams] = None,
    ) -> None:
        self.stock_metrics = stock_metrics
        if params is None:
            self.params = get_params(stock_metrics, projection_years)
        else:
            roe_params: ROEParameters = params
            roe_params.projection_years = projection_years
            self.params = roe_params

    def execute_valuation_scenarios(self) -> ROEValuationReport:
        valuation_report = execute_roe_scenarios(self.stock_metrics, self.params)
        self.report = valuation_report
        return valuation_report

    def get_default_params(self) -> ROEParameters:
        return get_params(self.stock_metrics, self.params.projection_years)

    def validate_metrics(self) -> ValuationCheckResult:
        return ROEChecker(self.stock_metrics).evaluate()