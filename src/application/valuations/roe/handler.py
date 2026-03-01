from typing import Optional
from domain.valuation.base import (
     ValuationParams, ValuationReport
)
from domain.valuation.policies import ValuationCheckResult
from domain.valuation.valuation_manager import ValuationManager
from domain.valuation.models.roe import ROEParameters
from domain.metrics.stock import StockMetrics
from .valuation import execute_roe_scenarios
from .defaults import get_params
from .validator import ROEChecker


class ROEManager(ValuationManager):
    report: Optional[ValuationReport] = None
    stock_metrics: StockMetrics
    params: ROEParameters

    def __init__(
        self,
        stock_metrics: StockMetrics,
        projection_years: int = 10,
        params: Optional[ValuationParams] = None
    ) -> None:
        self.set_valuation(stock_metrics, projection_years, params)

    def set_valuation(
        self,
        stock_metrics: StockMetrics,
        projection_years: int = 10,
        params: Optional[ValuationParams] = None
    ) -> None:
        self.stock_metrics = stock_metrics

        roe_params: ROEParameters

        if params is None:
            roe_params = ROEParameters(projection_years=projection_years)
            self.params = roe_params
            self.params = self.get_default_params()
        else:
            roe_params = params
            roe_params.projection_years = projection_years
            self.params = roe_params

    def execute_valuation_scenarios(self) -> ValuationReport:
        valuation_report = execute_roe_scenarios(self.stock_metrics, self.params)
        self.report = valuation_report
        return valuation_report

    def get_default_params(self) -> ValuationParams:
        return get_params(self.stock_metrics, self.params.projection_years)

    
    def validate_metrics(self) -> ValuationCheckResult:
        return ROEChecker(self.stock_metrics).evaluate()