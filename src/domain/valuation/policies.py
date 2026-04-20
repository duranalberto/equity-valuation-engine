from typing import List, Optional, Protocol, Union, runtime_checkable
from dataclasses import dataclass
from enum import Enum

from domain.metrics.stock import StockMetrics


class FactorSeverity(Enum):
    CRITICAL = "CRITICAL"
    WARNING  = "WARNING"
    INFO     = "INFO"


@dataclass(frozen=True)
class CheckFactor:
    name:     str
    message:  str
    severity: FactorSeverity
    weight:   int
    value:    Optional[Union[float, int]] = None


@dataclass(frozen=True)
class ValuationCheckResult:
    ticker:               str
    is_suitable:          bool
    total_severity_score: int
    interpretation:       str
    factors:              List[CheckFactor]


@runtime_checkable
class ValuationChecker(Protocol):
    """
    Protocol that all suitability-checker classes must satisfy.

    ``registry`` is optional so that callers which do not need
    reason-differentiated severity can omit it.  All three concrete
    implementations (``DCFChecker``, ``PEChecker``, ``ROEChecker``) accept
    ``(stock_metrics, registry=None)`` and satisfy this protocol.
    """

    def __init__(
        self,
        stock_metrics: StockMetrics,
        registry=None,      # Optional[MissingValueRegistry] — kept untyped here
    ) -> None:              # to avoid a circular import through domain/core
        ...

    def evaluate(self) -> ValuationCheckResult:
        ...
