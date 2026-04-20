from typing import Optional

from domain.core.missing_registry import MissingValueRegistry
from domain.metrics.stock import StockMetrics
from domain.valuation.models.pe import PEParameters, PEValuationReport
from domain.valuation.policies import ValuationCheckResult
from domain.valuation.valuation_manager import ValuationManager

from .defaults import get_params
from .validator import PEChecker
from .valuation import execute_pe_scenarios


class PEManager(ValuationManager[PEValuationReport]):
    """
    Orchestrates P/E valuation: parameter resolution, scenario execution,
    and pre-flight suitability checking.
    """

    stock_metrics: StockMetrics
    params: PEParameters

    def __init__(
        self,
        stock_metrics: StockMetrics,
        projection_years: int = 10,
        params: Optional[PEParameters] = None,
    ) -> None:
        self.report: Optional[PEValuationReport] = None
        self.set_valuation(stock_metrics, projection_years, params)

    def set_valuation(
        self,
        stock_metrics: StockMetrics,
        projection_years: int = 10,
        params: Optional[PEParameters] = None,
    ) -> None:
        self.stock_metrics = stock_metrics
        if params is None:
            self.params = get_params(stock_metrics, projection_years)
        else:
            params.projection_years = projection_years
            self.params = params

    def execute_valuation_scenarios(self) -> PEValuationReport:
        valuation_report = execute_pe_scenarios(self.stock_metrics, self.params)
        self.report = valuation_report
        return valuation_report

    def get_default_params(self) -> PEParameters:
        return get_params(self.stock_metrics, self.params.projection_years)

    def validate_metrics(
        self,
        registry: Optional[MissingValueRegistry] = None,
    ) -> ValuationCheckResult:
        return PEChecker(self.stock_metrics, registry).evaluate()
