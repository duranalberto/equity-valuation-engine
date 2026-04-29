from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from domain.valuation.base import GrowthAssumption, ValuationParams, ValuationReport


@dataclass
class ROEParameters(ValuationParams):
    """
    Parameters for ROE valuation.

    ``discount_rate`` is the rate used to discount dividends and terminal
    value back to the present.

    ``roe_cap`` (BUG-C fix) — optional ceiling applied to return_on_equity
    before computing terminal income.  Prevents leverage-inflated ROE from
    compounding unconstrained over the projection window.

    DESIGN-A/B: ``growth_model`` and ``reversion_enabled`` are inherited from
    ValuationParams and forwarded to generate_growth_scenarios().
    """
    discount_rate: float = 0.09
    # BUG-C: sector-specific cap loaded from config in defaults.py when None.
    roe_cap: Optional[float] = None


@dataclass
class ROEValuationInput:
    from domain.metrics.stock import StockMetrics
    stock_metrics:           StockMetrics
    dividend_rate_per_share: float
    growth_rates:            List[float]
    params:                  ROEParameters
    # BUG-B: propagated from execute_roe_scenarios() so roe_valuation() can
    # stamp the flag on the result without needing to re-inspect cash flow.
    buyback_substituted: bool = False


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
    # BUG-B: flag set True when buyback yield was used in place of dividends.
    buyback_substituted: bool = False
    # BUG-C: flag + value to surface capped ROE in output and presenters.
    roe_was_capped: bool = False
    roe_applied: Optional[float] = None


@dataclass
class ROEValuationReport(ValuationReport):
    scenarios:         Dict[str, ROEValuationResult]
    params:            ROEParameters
    growth_assumption: GrowthAssumption
