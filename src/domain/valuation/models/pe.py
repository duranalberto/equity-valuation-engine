from dataclasses import dataclass
from typing import List
from ..base import ValuationResult, ValuationInput, ValuationParams


@dataclass
class PEParameters(ValuationParams):
    margin_of_sefty: float = 0.20
    discount_rate: float = 0.10
    projection_years: int = 10


@dataclass
class PEValuationInput(ValuationInput):
    params: PEParameters


@dataclass
class PEValuationResult(ValuationResult):
    eps_progression: List[float]
    value_in_x_years: float
    present_value: float

