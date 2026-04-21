from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Protocol, Union, runtime_checkable


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

    Construction signature compatibility is intentional but not
    runtime-enforceable through the Protocol.  All concrete implementations
    (``DCFChecker``, ``PEChecker``, ``ROEChecker``) accept
    ``(stock_metrics, registry=None)`` by convention.
    """

    def evaluate(self) -> ValuationCheckResult:
        ...