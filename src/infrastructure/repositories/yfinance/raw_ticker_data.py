from __future__ import annotations

import logging
from typing import Any

import yfinance as yf

from .value_objects import RawTickerData

logger = logging.getLogger(__name__)


def fetch_raw_ticker_data(ticker_symbol: str) -> RawTickerData:
    """
    Fetch all raw data from yfinance for *ticker_symbol* and return it in a
    ``RawTickerData`` container.

    Every field is fetched defensively — a failure on one attribute does not
    prevent the others from being populated.
    """
    ticker = yf.Ticker(ticker_symbol)
    raw    = RawTickerData(ticker=ticker_symbol)

    def _safe(attr: str, call) -> Any:
        try:
            value = call()
            if value is None:
                logger.debug("yfinance returned None for %s.%s", ticker_symbol, attr)
            return value
        except Exception as exc:
            logger.warning(
                "Failed to fetch %s.%s from yfinance: %s",
                ticker_symbol, attr, exc,
            )
            return None

    raw.info           = _safe("info",          lambda: ticker.info)
    raw.fast_info      = _safe("fast_info",     lambda: ticker.fast_info)
    raw.income_stmt_q  = _safe("income_stmt_q", lambda: ticker.quarterly_income_stmt)
    raw.income_stmt_a  = _safe("income_stmt_a", lambda: ticker.income_stmt)
    raw.balance_sheet_q = _safe("bs_q",         lambda: ticker.quarterly_balance_sheet)
    raw.balance_sheet_a = _safe("bs_a",         lambda: ticker.balance_sheet)
    raw.cash_flow_q    = _safe("cf_q",          lambda: ticker.quarterly_cash_flow)
    raw.cash_flow_a    = _safe("cf_a",          lambda: ticker.cash_flow)
    raw.history        = _safe("history",       lambda: ticker.history(period="5y"))

    return raw
