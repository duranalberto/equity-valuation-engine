from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class ValuationParams:
    projection_years: int
    margin_of_safety: float
    discount_rate:    float


@dataclass
class ValuationInput:
    growth_rates: List[float]


@dataclass
class ValuationResult:
    growth_rates:     List[float]
    valuation_status: str


@dataclass
class ValuationReport:
    pass
