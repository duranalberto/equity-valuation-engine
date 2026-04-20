from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from domain.metrics.valuation import DiscountedCashFlow, WACC
from domain.valuation.base import ValuationParams, ValuationReport


@dataclass
class DCFParameters(ValuationParams):
    risk_free_rate:       float = 0.04
    market_risk_premium:  float = 0.055
    terminal_growth_rate: float = 0.02
    discount_rate:        float = field(init=False)

    def __post_init__(self):
        # discount_rate is not used in DCF directly (WACC takes its role)
        # but ValuationParams requires it; set to 0.0 as a placeholder.
        self.discount_rate = 0.0


@dataclass
class DCFInputData:
    from domain.metrics.stock import StockMetrics
    stock_metrics: StockMetrics
    growth_rates:  List[float]
    wacc:          WACC
    params:        DCFParameters


@dataclass
class DCFValuationResult:
    growth_rates:            List[float]
    valuation_status:        str
    fcf_projections:         List[float]
    dcf:                     DiscountedCashFlow
    intrinsic_value_per_share: float
    implied_wacc:            float


@dataclass
class DCFSensitivityReport:
    wacc_values:             List[float]
    terminal_growth_values:  List[float]
    intrinsic_values:        List[List[Optional[float]]]
    base_wacc:               float
    base_terminal_growth:    float
    scenario_name:           str = "Base"


@dataclass
class DCFValuationReport(ValuationReport):
    scenarios:   Dict[str, DCFValuationResult]
    params:      DCFParameters
    wacc:        WACC
    sensitivity: Optional[DCFSensitivityReport] = None
