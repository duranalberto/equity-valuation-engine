"""
YfinanceDataLoader — public-facing façade over YfinanceFetcher + YfinanceParser.

All application code continues to instantiate ``YfinanceDataLoader(ticker)``
exactly as before.  Internally it now delegates to:

    YfinanceFetcher  →  RawTickerData  →  YfinanceParser

Typical usage::

    loader = YfinanceDataLoader("AAPL")
    metrics = MetricsLoader("AAPL", loader_cls=YfinanceDataLoader).build_stock_metrics()

Test usage (no network)::

    from infrastructure.repositories.yfinance.raw_ticker_data import empty_raw
    raw = empty_raw("AAPL")
    # ... populate raw.quarterly_income with fixture DataFrames ...
    parser = YfinanceParser(raw)
    metrics = MetricsLoader.__new__(MetricsLoader)
    metrics.loader = parser
    metrics.mapper = parser.mapper
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from infrastructure.repositories.financial_repository import (
    BaseField, FinancialField, Period,
)
from infrastructure.mappers.stock_metrics_mapper import BaseStockMetricsMapper

from .raw_ticker_data import RawTickerData
from .value_objects import DataQuality
from .yfinance_fetcher import YfinanceFetcher
from .yfinance_parser import YfinanceParser

logger = logging.getLogger(__name__)


class YfinanceDataLoader:
    """
    Backward-compatible façade: fetch + parse in one constructor call.

    Delegates every ``FinancialRepository`` method to an internal
    ``YfinanceParser`` instance.  The public interface is identical to the
    old monolithic ``YfinanceDataLoader``, so no call-site changes are needed.
    """

    def __init__(self, ticker_symbol: str) -> None:
        raw: RawTickerData = YfinanceFetcher(ticker_symbol).fetch()
        self._parser = YfinanceParser(raw)

    @property
    def mapper(self) -> BaseStockMetricsMapper:
        return self._parser.mapper

    def get_label(self, field: BaseField) -> Optional[Any]:
        return self._parser.get_label(field)

    def get_ttm_from_quarters(
        self, field: FinancialField, year_offset: int = 0
    ) -> Optional[float]:
        return self._parser.get_ttm_from_quarters(field, year_offset)

    def get_annual_value(
        self, field: FinancialField, year_offset: int = 0
    ) -> Optional[float]:
        return self._parser.get_annual_value(field, year_offset)

    def get_latest_numeric(self, field: FinancialField) -> Optional[float]:
        return self._parser.get_latest_numeric(field)

    def get_series(
        self,
        field: FinancialField,
        period: Optional[Period] = None,
    ) -> Optional[List[float]]:
        return self._parser.get_series(field, period)

    def get_highest_price(self) -> Optional[float]:
        return self._parser.get_highest_price()

    def get_price_history(self) -> Optional[List[float]]:
        return self._parser.get_price_history()

    def get_eps_history(self) -> Optional[List[float]]:
        return self._parser.get_eps_history()

    def get_eps_data_quality(self) -> DataQuality:
        return self._parser.get_eps_data_quality()

    def debug_financial_coverage(self) -> Dict[str, Any]:
        return self._parser.debug_financial_coverage()
