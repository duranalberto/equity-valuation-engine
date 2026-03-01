from dataclasses import dataclass
from typing import List
from ..base import ValuationResult, ValuationInput, ValuationParams


@dataclass
class ROEParameters(ValuationParams):
    margin_of_safty: float = 0.20 
    discount_rate: float = 0.10
    projection_years: int = 10


@dataclass
class ROEValuationInput(ValuationInput):
    dividend_rate_per_share: float
    params: ROEParameters


@dataclass
class ROEValuationResult(ValuationResult):
    shareholders_equity_progression: List[float]
    dividend_progression: List[float]
    npv_dividend_progression: List[float]
    year_n_income: float
    required_value: float
    npv_required_value: float
    npv_dividends: float
    intrisic_value: float

