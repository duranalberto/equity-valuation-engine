from typing import Optional

from domain.core.missing_registry import MissingValueRegistry
from domain.metrics.stock import StockMetrics
from domain.valuation.models.ev_ebitda import EVEBITDAParameters, EVEBITDAValuationReport
from domain.valuation.policies import ValuationCheckResult
from domain.valuation.valuation_manager import ValuationManager

from .defaults import get_params
from .validator import EVEBITDAChecker
from .valuation import execute_ev_ebitda_scenarios


class EVEBITDAManager(ValuationManager[EVEBITDAValuationReport]):
    """
    Orchestrates EV/EBITDA relative valuation.
    """

    def __init__(
        self,
        stock_metrics: StockMetrics,
        projection_years: int = 10,
        params: Optional[EVEBITDAParameters] = None,
    ) -> None:
        self.report: Optional[EVEBITDAValuationReport] = None
        self.set_valuation(stock_metrics, projection_years, params)

    def set_valuation(
        self,
        stock_metrics: StockMetrics,
        projection_years: int = 10,
        params: Optional[EVEBITDAParameters] = None,
    ) -> None:
        self.stock_metrics = stock_metrics
        self.params = params if params is not None else get_params(stock_metrics, projection_years)
        self.params.projection_years = projection_years

    def execute_valuation_scenarios(self) -> EVEBITDAValuationReport:
        self.report = execute_ev_ebitda_scenarios(self.stock_metrics, self.params)
        return self.report

    def get_default_params(self) -> EVEBITDAParameters:
        return get_params(self.stock_metrics, self.params.projection_years)

    def validate_metrics(
        self,
        registry: Optional[MissingValueRegistry] = None,
    ) -> ValuationCheckResult:
        return EVEBITDAChecker(self.stock_metrics, registry).evaluate()
