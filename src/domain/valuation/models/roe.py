from dataclasses import dataclass
from typing import List
from ..base import ValuationResult, ValuationInput, ValuationParams, ValuationReport


@dataclass
class ROEParameters(ValuationParams):
    margin_of_safety: float = 0.20
    discount_rate: float = 0.10
    projection_years: int = 10


@dataclass
class ROEValuationInput(ValuationInput):
    dividend_rate_per_share: float
    params: ROEParameters


@dataclass
class ROEValuationResult(ValuationResult):
    growth_rates: List[float]
    valuation_status: str
    shareholders_equity_progression: List[float]
    dividend_progression: List[float]
    npv_dividend_progression: List[float]
    year_n_income: float
    required_value: float
    npv_required_value: float
    npv_dividends: float
    intrinsic_value: float


@dataclass
class ROEValuationReport(ValuationReport[ROEValuationResult]):
    params: ROEParameters
