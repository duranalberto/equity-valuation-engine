from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from domain.valuation.base import ValuationParams, ValuationReport


@dataclass
class EVEBITDAParameters(ValuationParams):
    """
    Parameters for EV/EBITDA relative valuation.

    ``discount_rate`` is absent — this is a market-multiple model;
    the "discount" is implicit in the multiple percentile chosen.

    DESIGN-B: ``reversion_enabled`` is inherited from ValuationParams.
    """
    pass   # all needed params come from ValuationParams + multiples.yaml


@dataclass
class EVEBITDAValuationInput:
    from domain.metrics.stock import StockMetrics
    stock_metrics:  StockMetrics
    ebitda_multiple: float      # Bear/Base/Bull multiple loaded from config
    params:         EVEBITDAParameters
    scenario:       str         # "Bear" | "Base" | "Bull"


@dataclass
class EVEBITDAValuationResult:
    scenario:                 str
    ebitda_multiple_used:     float
    intrinsic_ev:             float
    equity_value:             float
    intrinsic_value_per_share: float
    valuation_status:          str
    # Equity bridge components for transparency
    total_debt:               float
    cash_and_equivalents:     float


@dataclass
class EVEBITDAValuationReport(ValuationReport):
    scenarios: Dict[str, EVEBITDAValuationResult]
    params:    EVEBITDAParameters
    ebitda_ttm: float
