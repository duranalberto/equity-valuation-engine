from typing import Optional

from domain.core.missing_registry import MissingValueRegistry
from domain.metrics.stock import StockMetrics
from domain.valuation.models.reverse_dcf import ReverseDCFParameters, ReverseDCFReport
from domain.valuation.policies import ValuationCheckResult
from domain.valuation.valuation_manager import ValuationManager

from .defaults import get_params
from .validator import ReverseDCFChecker
from .valuation import solve_reverse_dcf


class ReverseDCFManager(ValuationManager[ReverseDCFReport]):
    """
    Orchestrates Reverse DCF (implied growth rate back-solver).

    Note: execute_valuation_scenarios() returns a ReverseDCFReport (not a
    multi-scenario dict).  The report contains a single ReverseDCFResult
    plus verification data.  The ValuationSummaryReport extractor in
    cli/main.py skips Reverse DCF from the composite IV (it is forensic,
    not an intrinsic model).
    """

    def __init__(
        self,
        stock_metrics: StockMetrics,
        projection_years: int = 10,
        params: Optional[ReverseDCFParameters] = None,
    ) -> None:
        self.report: Optional[ReverseDCFReport] = None
        self.set_valuation(stock_metrics, projection_years, params)

    def set_valuation(
        self,
        stock_metrics: StockMetrics,
        projection_years: int = 10,
        params: Optional[ReverseDCFParameters] = None,
    ) -> None:
        self.stock_metrics = stock_metrics
        self.params = params if params is not None else get_params(stock_metrics, projection_years)
        self.params.projection_years = projection_years

    def execute_valuation_scenarios(self) -> ReverseDCFReport:
        self.report = solve_reverse_dcf(self.stock_metrics, self.params)
        return self.report

    def get_default_params(self) -> ReverseDCFParameters:
        return get_params(self.stock_metrics, self.params.projection_years)

    def validate_metrics(
        self,
        registry: Optional[MissingValueRegistry] = None,
    ) -> ValuationCheckResult:
        return ReverseDCFChecker(self.stock_metrics, registry).evaluate()
