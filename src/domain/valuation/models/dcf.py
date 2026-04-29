from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from domain.metrics.valuation import WACC, DiscountedCashFlow
from domain.valuation.base import ValuationParams, ValuationReport


@dataclass
class DCFParameters(ValuationParams):
    """
    Parameters for DCF valuation.

    ``discount_rate`` is absent — DCF uses WACC (computed from market
    structure) in place of a fixed discount rate.  ``ValuationParams`` no
    longer carries ``discount_rate`` for the same reason.
    """
    risk_free_rate:       float = 0.04
    market_risk_premium:  float = 0.055
    terminal_growth_rate: float = 0.02


@dataclass
class DCFInputData:
    from domain.metrics.stock import StockMetrics
    stock_metrics: StockMetrics
    growth_rates:  List[float]
    wacc:          WACC
    params:        DCFParameters


@dataclass
class DCFValuationResult:
    growth_rates:              List[float]
    valuation_status:          str
    fcf_projections:           List[float]
    fcf_seed_source:           str
    dcf:                       DiscountedCashFlow
    intrinsic_value_per_share: float
    implied_wacc:              float
    # BUG-E fix: expose the 3-year average FCF used as the terminal value seed.
    # Previously this was an undisclosed smoothing detail inside _terminal_value_gordon().
    # Surfacing it allows analysts to see why the TV base differs from year-N FCF.
    fcf_tv_seed: Optional[float] = None


@dataclass
class DCFSensitivityReport:
    wacc_values:            List[float]
    terminal_growth_values: List[float]
    intrinsic_values:       List[List[Optional[float]]]
    base_wacc:              float
    base_terminal_growth:   float
    scenario_name:          str = "Base"
    # DESIGN-C fix: expose dynamically derived spreads so consumers can see
    # why the sensitivity grid has the range it does.
    derived_wacc_spread:    Optional[float] = None   # = f(beta)
    derived_tgr_spread:     Optional[float] = None   # = f(sector terminal_growth variance)


@dataclass
class DCFValuationReport(ValuationReport):
    scenarios:   Dict[str, DCFValuationResult]
    params:      DCFParameters
    wacc:        WACC
    sensitivity: Optional[DCFSensitivityReport] = None