from dataclasses import dataclass
from typing import Dict, Generic, List, TypeVar

from ..metrics.stock import StockMetrics


@dataclass
class ValuationParams:
    projection_years: int = 10

@dataclass
class ValuationInput:
    stock_metrics: StockMetrics
    growth_rates: List[float]
    params: ValuationParams

@dataclass
class ValuationResult:
    growth_rates: List[float]
    valuation_status: str

TValuationResult = TypeVar("TValuationResult", bound=ValuationResult)

@dataclass
class ValuationReport(Generic[TValuationResult]):
    scenarios: Dict[str, TValuationResult]
    params: ValuationParams
