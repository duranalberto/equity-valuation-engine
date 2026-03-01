from dataclasses import dataclass
from typing import Protocol, Dict, List
from ..metrics.stock import StockMetrics

@dataclass
class ValuationParams(Protocol):
    projection_years: int

@dataclass
class ValuationInput:
    stock_metrics: StockMetrics
    growth_rates: List[float]
    params: ValuationParams

    
@dataclass
class ValuationResult(Protocol):
    growth_rates: List[float]
    valuation_status: str


@dataclass
class ValuationReport:
    scenarios: Dict[str, ValuationResult]
    params: ValuationParams
    

