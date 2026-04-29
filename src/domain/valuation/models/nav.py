from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from domain.valuation.base import ValuationParams, ValuationReport


@dataclass
class NAVParameters(ValuationParams):
    """
    Parameters for Asset-Based / Net Asset Value model.

    ``discount_rate`` is absent — NAV is balance-sheet based; no discounting.
    ``asset_haircut`` is loaded from nav.yaml per scenario/sector.

    DESIGN-B: ``reversion_enabled`` inherited (not used for NAV projections,
    preserved for interface consistency).
    """
    pass


@dataclass
class NAVValuationResult:
    scenario:                  str
    asset_haircut_used:        float
    adjusted_assets:           float    # total_assets × haircut
    total_liabilities:         float
    nav:                       float    # adjusted_assets − total_liabilities
    nav_per_share:             float    # nav / shares_outstanding
    price_to_nav:              float    # current_price / nav_per_share
    intrinsic_value_per_share: float    # = nav_per_share (alias for summary table)
    valuation_status:           str
    goodwill_and_intangibles:   float
    intangible_asset_ratio:     float
    intangible_warning:        bool     # True when intangibles > intangible_cap


@dataclass
class NAVValuationReport(ValuationReport):
    scenarios:        Dict[str, NAVValuationResult]
    params:           NAVParameters
    total_assets:     float
    total_liabilities: float
    total_equity:     float
    goodwill_and_intangibles: float = 0.0
    intangible_asset_ratio:   float = 0.0
    intangible_cap:           float = 0.0
