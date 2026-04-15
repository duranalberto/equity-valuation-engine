"""
domain/metrics/history.py
=========================
Companion dataclasses that hold **full historical time-series** for each
financial statement.  They are designed to live alongside the scalar fields
already present on ``Financials``, ``CashFlow``, and ``BalanceSheet`` — not
to replace them.

Design principles
-----------------
* **Oldest-first ordering** — ``series[0]`` is the earliest observation,
  ``series[-1]`` is the most recent.  This matches ``HistoricalData.price_history``
  and ``HistoricalData.eps_history``.
* **Optional[List[float]]** for every field — ``None`` means "not loaded /
  not available".  An empty list is never stored (the loader returns ``None``
  instead).
* **No FX logic** — FX conversion is applied at extraction time by the loader,
  identical to all other numeric fields.
* **Derived series** (e.g. ``fcf_*``) are computed in ``__post_init__`` from
  their component series, mirroring the pattern used in ``CashFlow``.
* **Quarterly and annual** variants are kept separate so callers can choose the
  appropriate granularity for their calculation.

Attachment
----------
Each companion is attached as an optional ``.history`` field on the
corresponding primary dataclass (``Financials``, ``CashFlow``,
``BalanceSheet``).  Existing code that only uses scalar fields is completely
unaffected.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


def _normalize_capex_series(series: Optional[List[float]]) -> Optional[List[float]]:
    if series is None:
        return None
    return [-abs(float(value)) for value in series]


@dataclass
class FinancialsHistory:
    """
    Full quarterly and annual time-series for the income statement.

    Quarterly fields provide 8–16 data points from yfinance; annual fields
    provide 4 data points.  Both are oldest-first.

    The ``da_quarterly`` field carries Depreciation & Amortisation from the
    cash-flow statement (same source as ``Financials.da_ttm``).
    """
    
    revenue_quarterly:          Optional[List[float]] = None
    gross_profit_quarterly:     Optional[List[float]] = None
    operating_income_quarterly: Optional[List[float]] = None
    net_income_quarterly:       Optional[List[float]] = None
    ebit_quarterly:             Optional[List[float]] = None
    ebt_quarterly:              Optional[List[float]] = None
    tax_expense_quarterly:      Optional[List[float]] = None
    interest_expense_quarterly: Optional[List[float]] = None
    da_quarterly:               Optional[List[float]] = None
    
    revenue_annual:             Optional[List[float]] = None
    gross_profit_annual:        Optional[List[float]] = None
    operating_income_annual:    Optional[List[float]] = None
    net_income_annual:          Optional[List[float]] = None
    ebit_annual:                Optional[List[float]] = None
    ebt_annual:                 Optional[List[float]] = None
    tax_expense_annual:         Optional[List[float]] = None
    interest_expense_annual:    Optional[List[float]] = None

@dataclass
class CashFlowHistory:
    """
    Full quarterly and annual time-series for the cash-flow statement.

    ``fcf_quarterly`` and ``fcf_annual`` are derived from their components
    in ``__post_init__``, exactly as ``CashFlow.fcf_ttm`` is derived from
    ``operating_cf_ttm`` and ``capex_ttm``.

    Note: capex values from yfinance can arrive with inconsistent signs
    across providers.  Capex series are normalized to negative outflows before
    deriving FCF, matching the scalar ``CashFlow`` model.
    """

    operating_cf_quarterly:   Optional[List[float]] = None
    capex_quarterly:          Optional[List[float]] = None
    dividends_paid_quarterly: Optional[List[float]] = None
    share_buybacks_quarterly: Optional[List[float]] = None

    operating_cf_annual:      Optional[List[float]] = None
    capex_annual:             Optional[List[float]] = None
    dividends_paid_annual:    Optional[List[float]] = None
    share_buybacks_annual:    Optional[List[float]] = None

    fcf_quarterly: Optional[List[float]] = field(default=None, init=False)
    fcf_annual:    Optional[List[float]] = field(default=None, init=False)

    def __post_init__(self) -> None:
        self.capex_quarterly = _normalize_capex_series(self.capex_quarterly)
        self.capex_annual = _normalize_capex_series(self.capex_annual)
        self.fcf_quarterly = _pairwise_sum(
            self.operating_cf_quarterly, self.capex_quarterly
        )
        self.fcf_annual = _pairwise_sum(
            self.operating_cf_annual, self.capex_annual
        )


@dataclass
class BalanceSheetHistory:
    """
    Full quarterly time-series for the balance sheet.

    Balance-sheet data is point-in-time (not a flow), so quarterly snapshots
    are the primary granularity.  Annual values are included for trend analysis
    across fiscal years.
    """

    total_debt_quarterly:              Optional[List[float]] = None
    total_equity_quarterly:            Optional[List[float]] = None
    cash_quarterly:                    Optional[List[float]] = None
    total_assets_quarterly:            Optional[List[float]] = None
    total_liabilities_quarterly:       Optional[List[float]] = None
    current_assets_quarterly:          Optional[List[float]] = None
    current_liabilities_quarterly:     Optional[List[float]] = None
    inventory_quarterly:               Optional[List[float]] = None

    total_debt_annual:                 Optional[List[float]] = None
    total_equity_annual:               Optional[List[float]] = None
    cash_annual:                       Optional[List[float]] = None
    total_assets_annual:               Optional[List[float]] = None


def _pairwise_sum(
    a: Optional[List[float]],
    b: Optional[List[float]],
) -> Optional[List[float]]:
    """
    Element-wise sum of two equal-length lists.

    Returns ``None`` when either list is ``None`` or the lists have different
    lengths (length mismatch indicates misaligned data).
    """
    if a is None or b is None:
        return None
    if len(a) != len(b):
        return None
    result = [x + y for x, y in zip(a, b)]
    return result if result else None
