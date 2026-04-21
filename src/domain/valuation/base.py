from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class ValuationParams:
    """
    Base parameters shared by all valuation models.

    ``discount_rate`` is intentionally absent here — it is meaningful only
    for PE and ROE models (where it discounts future earnings to present
    value) and is a concrete field on ``PEParameters`` and ``ROEParameters``
    respectively.  ``DCFParameters`` does not discount via a fixed rate;
    it uses WACC instead.
    """
    projection_years: int
    margin_of_safety: float


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