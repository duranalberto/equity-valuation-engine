from typing import Optional

from domain.metrics.stock import StockMetrics
from domain.valuation.models.dcf import DCFParameters, DCFValuationReport
from domain.valuation.policies import ValuationCheckResult
from domain.valuation.valuation_manager import ValuationManager

from .defaults import get_params
from .validator import DCFChecker
from .valuation import execute_dcf_scenarios


class DCFManager(ValuationManager[DCFValuationReport]):
    """
    Orchestrates DCF valuation: parameter resolution, scenario execution,
    and pre-flight suitability checking.
    """

    params: DCFParameters
    stock_metrics: StockMetrics

    def __init__(
        self,
        stock_metrics: StockMetrics,
        projection_years: int = 10,
        params: Optional[DCFParameters] = None,
    ) -> None:
        self.report: Optional[DCFValuationReport] = None
        self.set_valuation(stock_metrics, projection_years, params)

    def set_valuation(
        self,
        stock_metrics: StockMetrics,
        projection_years: int = 10,
        params: Optional[DCFParameters] = None,
    ) -> None:
        self.stock_metrics = stock_metrics
        if params is None:
            self.params = get_params(stock_metrics, projection_years)
        else:
            params.projection_years = projection_years
            self.params = params

    def execute_valuation_scenarios(self) -> DCFValuationReport:
        valuation_report = execute_dcf_scenarios(self.stock_metrics, self.params)
        self.report = valuation_report
        return valuation_report

    def get_default_params(self) -> DCFParameters:
        return get_params(self.stock_metrics, self.params.projection_years)

    def validate_metrics(self) -> ValuationCheckResult:
        return DCFChecker(self.stock_metrics).evaluate()