"""
YfinanceFetcher — the network I/O half of the old YfinanceDataLoader.

Responsibilities
----------------
* Call ``yf.Ticker`` exactly once.
* Collect every raw DataFrame and the info dict into a ``RawTickerData``.
* Apply no transformation, normalisation, or business logic.

Testing
-------
This class is the only place that should ever be mocked/recorded at the
HTTP level (e.g. with ``vcrpy`` or ``responses``).  A single cassette per
ticker is enough to cover every parser test because the fetcher is the
only network consumer.
"""
from __future__ import annotations

import logging
import warnings
from typing import Any, Dict, Optional

import pandas as pd
import yfinance as yf

from .raw_ticker_data import RawTickerData

logger = logging.getLogger(__name__)


class YfinanceFetcher:
    """
    Fetch raw data for a single ticker from Yahoo Finance.

    Usage::

        raw = YfinanceFetcher("AAPL").fetch()
        # raw is a RawTickerData — hand it to YfinanceParser

    The fetcher is intentionally stateless after ``fetch()`` returns.
    Nothing is cached here; caching is the caller's responsibility.
    """

    def __init__(self, ticker_symbol: str) -> None:
        if not ticker_symbol or not ticker_symbol.strip():
            raise ValueError("ticker_symbol must be a non-empty string.")
        self._symbol = ticker_symbol.strip().upper()

    def fetch(self) -> RawTickerData:
        """
        Call Yahoo Finance and return a ``RawTickerData``.

        Never raises — network errors are caught and logged; the returned
        object will have empty DataFrames and/or an empty info dict so the
        parser can handle the degraded case gracefully.
        """
        logger.info("Fetching yfinance data for %s", self._symbol)
        ticker = yf.Ticker(self._symbol)

        info = self._safe_info(ticker)
        annual = self._fetch_annual(ticker)
        quarterly = self._fetch_quarterly(ticker)
        earnings_raw = self._safe_earnings_history(ticker)
        price_raw = self._safe_price_history(ticker)

        return RawTickerData(
            ticker_symbol=self._symbol,
            info=info,
            annual_income=annual["income"],
            annual_cashflow=annual["cashflow"],
            annual_balance_sheet=annual["balance_sheet"],
            quarterly_income=quarterly["income"],
            quarterly_cashflow=quarterly["cashflow"],
            quarterly_balance_sheet=quarterly["balance_sheet"],
            earnings_history_raw=earnings_raw,
            price_history_raw=price_raw,
        )

    def _safe_info(self, ticker: yf.Ticker) -> Dict[str, Any]:
        try:
            info = ticker.info
            return info if isinstance(info, dict) else {}
        except Exception as exc:
            logger.warning("Could not fetch info for %s: %s", self._symbol, exc)
            return {}

    def _fetch_annual(self, ticker: yf.Ticker) -> Dict[str, pd.DataFrame]:
        return {
            "income": self._safe_df(ticker, "financials"),
            "cashflow": self._safe_df(ticker, "cashflow"),
            "balance_sheet": self._safe_df(ticker, "balance_sheet"),
        }

    def _fetch_quarterly(self, ticker: yf.Ticker) -> Dict[str, pd.DataFrame]:
        return {
            "income": self._safe_df(ticker, "quarterly_financials"),
            "cashflow": self._safe_df(ticker, "quarterly_cashflow"),
            "balance_sheet": self._safe_df(ticker, "quarterly_balance_sheet"),
        }

    def _safe_earnings_history(
        self, ticker: yf.Ticker
    ) -> Optional[pd.DataFrame]:
        try:
            raw = getattr(ticker, "earnings_history", None)
            if raw is None:
                return None
            if isinstance(raw, list):
                df = pd.DataFrame(raw)
            elif isinstance(raw, pd.DataFrame):
                df = raw.copy()
            else:
                return None
            return df if not df.empty else None
        except Exception as exc:
            logger.warning(
                "Could not fetch earnings_history for %s: %s", self._symbol, exc
            )
            return None

    def _safe_price_history(
        self, ticker: yf.Ticker
    ) -> Optional[pd.DataFrame]:
        try:
            df = ticker.history(period="max", interval="1mo")
            if isinstance(df, pd.DataFrame) and not df.empty:
                return df
            return None
        except Exception as exc:
            logger.warning(
                "Could not fetch price history for %s: %s", self._symbol, exc
            )
            return None

    @staticmethod
    def _safe_df(ticker: yf.Ticker, attr: str) -> pd.DataFrame:
        """Return the attribute as a DataFrame, or an empty DataFrame on error."""
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                value = getattr(ticker, attr, None)
            if value is None:
                return pd.DataFrame()
            if isinstance(value, pd.DataFrame):
                return value
            return pd.DataFrame(value)
        except Exception as exc:
            logger.warning(
                "Could not fetch %s.%s: %s", ticker.ticker, attr, exc
            )
            return pd.DataFrame()