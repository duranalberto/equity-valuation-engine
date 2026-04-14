from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Protocol, Dict, List, runtime_checkable
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

@dataclass
class ValuationReport:
    scenarios: Dict[str, ValuationResult]
    params: ValuationParams
