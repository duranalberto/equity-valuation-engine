from dataclasses import dataclass
from typing import List
from ...metrics.valuation import DiscountedCashFlow, WACC
from ..base import ValuationReport, ValuationParams, ValuationInput, ValuationResult


@dataclass
class DCFParameters(ValuationParams):
    margin_of_safety: float = 0.20
    risk_free_rate: float = 0.045
    market_risk_premium: float = 0.060
    terminal_growth_rate: float = 0.025
    projection_years: int = 10


@dataclass
class DCFInputData(ValuationInput):
    wacc: WACC
    params: DCFParameters


@dataclass
class DCFValuationResult(ValuationResult):
    growth_rates: List[float]
    valuation_status: str
    fcf_projections: List[float]
    dcf: DiscountedCashFlow
    intrinsic_value_per_share: float
    implied_wacc: float


@dataclass
class DCFValuationReport(ValuationReport):
    wacc: WACC
