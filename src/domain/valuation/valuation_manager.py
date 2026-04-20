from abc import ABC, abstractmethod
from typing import Generic, Optional, TypeVar

from domain.core.missing_registry import MissingValueRegistry
from domain.metrics.stock import StockMetrics
from domain.valuation.base import ValuationParams, ValuationReport
from domain.valuation.policies import ValuationCheckResult

TReport = TypeVar("TReport", bound=ValuationReport)


class ValuationManager(ABC, Generic[TReport]):
    """
    Abstract base for all valuation managers.

    ``validate_metrics`` accepts an optional ``MissingValueRegistry`` so that
    checkers can produce reason-differentiated factor severity (e.g. a field
    missing because it is ``NOT_APPLICABLE`` → ``WARNING`` rather than
    ``CRITICAL``).
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
    def validate_metrics(
        self,
        registry: Optional[MissingValueRegistry] = None,
    ) -> ValuationCheckResult:
        pass
