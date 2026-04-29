from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from domain.valuation.base import ValuationParams, ValuationReport


@dataclass
class DDMParameters(ValuationParams):
    """
    Parameters for Gordon Growth DDM.

    ``risk_free_rate`` and ``market_risk_premium`` feed CAPM to derive the
    required return (r).  ``terminal_growth_rate`` is the perpetual dividend
    growth rate used in the Gordon Growth formula: IV = D1 / (r − g).

    DESIGN-B: ``reversion_enabled`` inherited from ValuationParams.
    """
    risk_free_rate:       float = 0.04
    market_risk_premium:  float = 0.055
    terminal_growth_rate: float = 0.03


@dataclass
class DDMValuationResult:
    scenario:                  str
    growth_rates:              List[float]    # per-year dividend growth (projection window)
    dividend_progression:      List[float]    # D_1 … D_N projected dividends per share
    terminal_dividend:         float          # D_{N+1} = D_N × (1 + terminal_growth_rate)
    required_return:           float          # r from CAPM
    terminal_value:            float          # D_{N+1} / (r − g)
    pv_dividends:              float          # PV of projection-window dividends
    pv_terminal_value:         float          # PV of terminal value
    intrinsic_value_per_share: float          # pv_dividends + pv_terminal_value
    implied_required_return:   float          # back-solved r that makes IV = price
    dividend_yield_implied:    float          # D1 / intrinsic_value_per_share
    valuation_status:           str


@dataclass
class DDMValuationReport(ValuationReport):
    scenarios:           Dict[str, DDMValuationResult]
    params:              DDMParameters
    dps_ttm:             float   # dividend per share (TTM) — the D0 seed
    dividend_growth_rate: float  # historical CAGR used as growth signal
