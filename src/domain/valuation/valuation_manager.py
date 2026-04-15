from abc import ABC, abstractmethod
from typing import Generic, Optional, TypeVar

from ..metrics.stock import StockMetrics
from .base import ValuationParams, ValuationReport
from .policies import ValuationCheckResult

TReport = TypeVar("TReport", bound=ValuationReport)

class ValuationManager(ABC, Generic[TReport]):
    """
    Abstract base for all valuation managers.
    """

    stock_metrics: StockMetrics

    @abstractmethod
    def __init__(
        self,
        stock_metrics: StockMetrics,
        projection_years: int = 10,
        params: Optional[ValuationParams] = None,
    ) -> None:
        pass

    @abstractmethod
    def set_valuation(
        self,
        stock_metrics: StockMetrics,
        projection_years: int = 10,
        params: Optional[ValuationParams] = None,
    ) -> None:
        pass

    @abstractmethod
    def execute_valuation_scenarios(self) -> TReport:
        pass

    @abstractmethod
    def get_default_params(self) -> ValuationParams:
        pass

    @abstractmethod
    def validate_metrics(self) -> ValuationCheckResult:
        pass