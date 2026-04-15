from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from ...metrics.valuation import WACC, DiscountedCashFlow
from ..base import ValuationInput, ValuationParams, ValuationReport, ValuationResult


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
class DCFSensitivityReport:
    """
    2-D sensitivity table: WACC x terminal growth rate -> intrinsic value per share.

    Attributes
    ----------
    wacc_values
        List of WACC rates tested (axis rows), ascending.
    terminal_growth_values
        List of terminal growth rates tested (axis columns), ascending.
    intrinsic_values
        Matrix where intrinsic_values[i][j] is the intrinsic value per share
        at wacc_values[i] x terminal_growth_values[j].  A cell is None when
        the combination is numerically invalid (WACC <= terminal growth rate).
    base_wacc
        The base-case WACC used in the primary DCF run.
    base_terminal_growth
        The base-case terminal growth rate used in the primary DCF run.
    scenario_name
        Which scenario's FCF projections were used as the fixed input.
    """
    wacc_values:            List[float]
    terminal_growth_values: List[float]
    intrinsic_values:       List[List[Optional[float]]]
    base_wacc:              float
    base_terminal_growth:   float
    scenario_name:          str = "Base"


@dataclass
class DCFValuationReport(ValuationReport[DCFValuationResult]):
    wacc: WACC
    sensitivity: Optional[DCFSensitivityReport] = field(default=None)
