from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from domain.valuation.base import ValuationParams, ValuationReport


@dataclass
class ReverseDCFParameters(ValuationParams):
    """
    Parameters for Reverse DCF (implied growth rate back-solver).

    ``risk_free_rate``, ``market_risk_premium``, and ``terminal_growth_rate``
    feed CAPM→WACC (same as forward DCF).  The binary search bounds are
    fixed at [−0.10, 0.60] per the implementation plan.

    DESIGN-B: ``reversion_enabled`` inherited but not applied in Reverse DCF
    (the model back-solves from market price, not forward-projects).
    """
    risk_free_rate:       float = 0.04
    market_risk_premium:  float = 0.055
    terminal_growth_rate: float = 0.02
    search_low:           float = -0.10   # lower bound for binary search
    search_high:          float =  0.60   # upper bound for binary search


@dataclass
class ReverseDCFResult:
    """
    Result of the reverse DCF calculation.

    ``implied_growth_rate`` is the constant annual FCF growth rate that,
    when fed into a standard DCF, produces an intrinsic value equal to the
    current market price.

    ``implied_vs_forward_delta`` = implied − forward_growth_rate
      Positive → market prices in more growth than historical signals suggest
      Negative → market prices in less growth (potentially undervalued)

    ``interpretation`` provides a human-readable assessment.
    """
    implied_growth_rate:       float
    implied_vs_forward_delta:  float   # implied − forward_growth_rate
    wacc:                      float
    terminal_growth_rate:      float
    fcf_seed:                  float   # FCF used as projection seed
    fcf_seed_source:           str     # "raw" | "normalized"
    interpretation:            str
    # Verification: feeding implied_growth_rate back into DCF should ≈ current_price
    verification_iv:           Optional[float] = None
    verification_error_pct:    Optional[float] = None   # |IV − price| / price


@dataclass
class ReverseDCFReport(ValuationReport):
    result:        ReverseDCFResult
    params:        ReverseDCFParameters
    current_price: float
    ticker:        str
