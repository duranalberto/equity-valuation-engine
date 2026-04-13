"""
RawTickerData — the boundary value object produced by YfinanceFetcher
and consumed by YfinanceParser.

Keeping this as a frozen dataclass enforces that the fetcher's output is
immutable before it reaches the parser. Tests can construct instances
directly from fixture DataFrames with no network dependency.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import pandas as pd


@dataclass(frozen=True)
class RawTickerData:
    """
    Everything the yfinance API returns for a single ticker, in raw form.

    Fields
    ------
    ticker_symbol
        The normalised (upper-case, stripped) symbol used to fetch.
    info
        The ``ticker.info`` dict from yfinance.  Never None — an empty dict
        is used when yfinance fails so downstream code has a single safe path.
    annual_income : DataFrame
        Annual income statement (``ticker.financials``).
    annual_cashflow : DataFrame
        Annual cash-flow statement (``ticker.cashflow``).
    annual_balance_sheet : DataFrame
        Annual balance sheet (``ticker.balance_sheet``).
    quarterly_income : DataFrame
        Quarterly income statement (``ticker.quarterly_financials``).
    quarterly_cashflow : DataFrame
        Quarterly cash-flow statement (``ticker.quarterly_cashflow``).
    quarterly_balance_sheet : DataFrame
        Quarterly balance sheet (``ticker.quarterly_balance_sheet``).
    earnings_history_raw : DataFrame | None
        Raw earnings-history frame from ``ticker.earnings_history``, if
        available.  None when the attribute is absent or empty.
    price_history_raw : DataFrame | None
        Monthly OHLCV history from ``ticker.history(period="max",
        interval="1mo")``.  None when unavailable.
    """

    ticker_symbol: str
    info: Dict[str, Any]

    annual_income: pd.DataFrame
    annual_cashflow: pd.DataFrame
    annual_balance_sheet: pd.DataFrame
    quarterly_income: pd.DataFrame
    quarterly_cashflow: pd.DataFrame
    quarterly_balance_sheet: pd.DataFrame

    earnings_history_raw: Optional[pd.DataFrame]
    price_history_raw: Optional[pd.DataFrame]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RawTickerData):
            return NotImplemented
        return (
            self.ticker_symbol == other.ticker_symbol
            and self.info == other.info
            and _df_eq(self.annual_income, other.annual_income)
            and _df_eq(self.annual_cashflow, other.annual_cashflow)
            and _df_eq(self.annual_balance_sheet, other.annual_balance_sheet)
            and _df_eq(self.quarterly_income, other.quarterly_income)
            and _df_eq(self.quarterly_cashflow, other.quarterly_cashflow)
            and _df_eq(self.quarterly_balance_sheet, other.quarterly_balance_sheet)
            and _df_eq(self.earnings_history_raw, other.earnings_history_raw)
            and _df_eq(self.price_history_raw, other.price_history_raw)
        )
    __hash__ = None


def _df_eq(a: Optional[pd.DataFrame], b: Optional[pd.DataFrame]) -> bool:
    """Structural equality for two optional DataFrames."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    if a.shape != b.shape:
        return False
    try:
        return bool((a.fillna(0) == b.fillna(0)).all().all())
    except Exception:
        return False

def empty_raw(ticker_symbol: str = "TEST") -> RawTickerData:
    """
    Return a RawTickerData with all DataFrames empty and an empty info dict.

    Useful as a base for test fixtures — override only the fields relevant
    to the behaviour under test.
    """
    empty = pd.DataFrame()
    return RawTickerData(
        ticker_symbol=ticker_symbol,
        info={},
        annual_income=empty,
        annual_cashflow=empty,
        annual_balance_sheet=empty,
        quarterly_income=empty,
        quarterly_cashflow=empty,
        quarterly_balance_sheet=empty,
        earnings_history_raw=None,
        price_history_raw=None,
    )