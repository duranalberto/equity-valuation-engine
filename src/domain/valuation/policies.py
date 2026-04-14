from domain.metrics.stock import StockMetrics
from typing import List, Union, Optional, Protocol, runtime_checkable
from dataclasses import dataclass
from enum import Enum

class FactorSeverity(Enum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"

@dataclass(frozen=True)
class CheckFactor:
    name: str
    message: str
    severity: FactorSeverity
    weight: int
    value: Optional[Union[float, int]] = None

@dataclass(frozen=True)
class ValuationCheckResult:
    ticker: str
    is_suitable: bool
    total_severity_score: int
    interpretation: str
    factors: List[CheckFactor]

@runtime_checkable
class ValuationChecker(Protocol):
    def __init__(self, stock_metrics: StockMetrics) -> None:
        ...

    def evaluate(self) -> ValuationCheckResult:
        ...
