from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from domain.valuation.base import ValuationParams, ValuationReport


@dataclass
class PEParameters(ValuationParams):
    """
    Parameters for P/E valuation.

    ``discount_rate`` is a concrete field here — it is the rate used to
    discount future EPS-based value back to the present.
    """
    discount_rate: float = 0.09


@dataclass
class PEValuationInput:
    from domain.metrics.stock import StockMetrics
    stock_metrics: StockMetrics
    growth_rates:  List[float]
    params:        PEParameters


@dataclass
class PEValuationResult:
    growth_rates:      List[float]
    valuation_status:  str
    eps_progression:   List[float]
    value_in_x_years:  float
    present_value:     float


@dataclass
class PEValuationReport(ValuationReport):
    scenarios: Dict[str, PEValuationResult]
    params:    PEParameters