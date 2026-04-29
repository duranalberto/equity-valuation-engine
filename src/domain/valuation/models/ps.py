from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from domain.valuation.base import ValuationParams, ValuationReport


@dataclass
class PSParameters(ValuationParams):
    """
    Parameters for P/S (Price/Sales) revenue multiple valuation.

    DESIGN-B: ``reversion_enabled`` inherited from ValuationParams.
    """
    pass   # multiples loaded from multiples.yaml


@dataclass
class PSValuationResult:
    scenario:                  str
    ps_multiple_used:          float
    intrinsic_market_cap:      float
    intrinsic_value_per_share: float
    valuation_status:           str
    implied_revenue_multiple:   float   # current market_cap / revenue_ttm for comparison
    revenue_ttm:               float


@dataclass
class PSValuationReport(ValuationReport):
    scenarios: Dict[str, PSValuationResult]
    params:    PSParameters
    revenue_ttm: float
