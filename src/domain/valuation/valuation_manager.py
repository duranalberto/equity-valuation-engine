
from abc import ABC, abstractmethod
from typing import Optional
from .base import ValuationParams, ValuationReport, ValuationInput, ValuationResult
from .policies import ValuationCheckResult
from ..metrics.stock import StockMetrics

class ValuationManager(ABC):
    report: Optional[ValuationReport] = None
    stock_metrics: StockMetrics
    
    @abstractmethod
    def __init__(
        self,
        stock_metrics: StockMetrics,
        projection_years: int = 10,
        params: Optional[ValuationParams] = None
    ) -> None:
        """
        Initializes the manager. Must be implemented by subclasses.
        """
        pass

    @abstractmethod
    def set_valuation(
        self,
        stock_metrics: StockMetrics,
        projection_years: int = 10,
        params: Optional[ValuationParams] = None
    ) -> None:
        pass

    @abstractmethod
    def execute_valuation_scenarios(self) -> ValuationReport:
        pass

    @abstractmethod
    def get_default_params(self) -> ValuationParams:
        pass

    @abstractmethod
    def validate_metrics(self) -> ValuationCheckResult:
        pass
