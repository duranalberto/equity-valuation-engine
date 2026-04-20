"""
Companion dataclasses that hold full historical time-series for each
financial statement.
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
    """Full quarterly and annual time-series for the income statement."""

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
    """Full quarterly and annual time-series for the cash-flow statement."""

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
        self.capex_annual    = _normalize_capex_series(self.capex_annual)
        self.fcf_quarterly   = _pairwise_sum(self.operating_cf_quarterly, self.capex_quarterly)
        self.fcf_annual      = _pairwise_sum(self.operating_cf_annual,    self.capex_annual)


@dataclass
class BalanceSheetHistory:
    """Full quarterly and annual time-series for the balance sheet."""

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
    if a is None or b is None:
        return None
    if len(a) != len(b):
        return None
    result = [x + y for x, y in zip(a, b)]
    return result if result else None
