from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from domain.valuation.base import ValuationParams, ValuationReport


@dataclass
class ROEParameters(ValuationParams):
    """
    Parameters for ROE valuation.

    ``discount_rate`` is a concrete field here — it is the rate used to
    discount dividends and terminal value back to the present.
    """
    discount_rate: float = 0.09


@dataclass
class ROEValuationInput:
    from domain.metrics.stock import StockMetrics
    stock_metrics:           StockMetrics
    dividend_rate_per_share: float
    growth_rates:            List[float]
    params:                  ROEParameters


@dataclass
class ROEValuationResult:
    growth_rates:                    List[float]
    valuation_status:                str
    shareholders_equity_progression: List[float]
    dividend_progression:            List[float]
    npv_dividend_progression:        List[float]
    year_n_income:                   float
    required_value:                  float
    npv_required_value:              float
    npv_dividends:                   float
    intrinsic_value:                 float


@dataclass
class ROEValuationReport(ValuationReport):
    scenarios: Dict[str, ROEValuationResult]
    params:    ROEParameters