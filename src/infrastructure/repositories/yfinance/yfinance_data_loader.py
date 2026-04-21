from __future__ import annotations

import logging
from typing import Any, List, Optional, Union

from infrastructure.mappers.stock_metrics_mapper import StockMetricsMapper
from infrastructure.repositories.financial_repository import (
    EnumField,
    FinancialField,
    LabelField,
    Period,
)

from .mappers.common_constants import INFO_LABELS
from .mappers.enum_mappers import map_sector
from .mappers.stock_metrics_mapper import build_stock_metrics_mapper
from .mappers.yfinance_fields import Statement
from .raw_ticker_data import fetch_raw_ticker_data
from .yfinance_fetcher import YfinanceFetcher
from .yfinance_parser import YfinanceParser

logger = logging.getLogger(__name__)


class YfinanceDataLoader:
    """
    Implements ``FinancialRepository`` using Yahoo Finance as the data source.

    Construction fetches all raw data once; subsequent calls read from the
    in-memory ``RawTickerData``.
    """

    def __init__(self, ticker_symbol: str) -> None:
        raw           = fetch_raw_ticker_data(ticker_symbol)
        self._fetcher = YfinanceFetcher(raw)
        self._parser  = YfinanceParser(self._fetcher)
        self._raw     = raw
        self._mapper  = build_stock_metrics_mapper()

    @property
    def mapper(self) -> StockMetricsMapper:
        return self._mapper

    def get_label(
        self,
        field: Union[LabelField, EnumField],
    ) -> Optional[Any]:
        if isinstance(field, EnumField):
            return map_sector(self._fetcher.get_info(field.label))

        label = field.label if isinstance(field.label, str) else None
        if label is None:
            return None

        method_name = self._INFO_LABEL_TO_PARSER_METHOD.get(label)
        if method_name:
            return getattr(self._parser, method_name)()

        return self._fetcher.get_info(label)

    def get_ttm_from_quarters(
        self,
        field: FinancialField,
        year_offset: int = 0,
    ) -> Optional[float]:
        labels = field.label if isinstance(field.label, list) else [field.label]
        df = self._select_df(field, Period.QUARTERLY)
        from .dataframe_utils import get_ttm_from_quarters
        return get_ttm_from_quarters(df, labels, year_offset)

    def get_annual_value(
        self,
        field: FinancialField,
        year_offset: int = 0,
    ) -> Optional[float]:
        labels = field.label if isinstance(field.label, list) else [field.label]
        df = self._select_df(field, Period.ANNUAL)
        from .dataframe_utils import get_annual_value
        return get_annual_value(df, labels, year_offset)

    def get_latest_numeric(
        self,
        field: FinancialField,
    ) -> Optional[float]:
        labels = field.label if isinstance(field.label, list) else [field.label]
        period = field.period if field.period is not None else Period.QUARTERLY
        df     = self._select_df(field, period)
        from .dataframe_utils import get_latest_numeric
        return get_latest_numeric(df, labels)

    def get_series(
        self,
        field: FinancialField,
        period: Optional[Period] = None,
    ) -> Optional[List[float]]:
        labels          = field.label if isinstance(field.label, list) else [field.label]
        resolved_period = period or field.period or Period.QUARTERLY
        df              = self._select_df(field, resolved_period)
        from .dataframe_utils import get_series
        return get_series(df, labels, ascending=True)

    def get_highest_price(self) -> Optional[float]:
        return self._parser.highest_price()

    def get_price_history(self) -> Optional[List[float]]:
        return self._parser.price_history()

    def get_eps_history(self) -> Optional[List[float]]:
        return self._parser.eps_history()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _select_df(self, field: FinancialField, period: Period):
        """
        Return the correct DataFrame for a given field and period.

        Routing is based on the ``statement`` attribute present on every
        ``YfFinancialField`` and ``YfSeriesField``.  This is an O(1) attribute
        lookup; it replaces the previous O(n) label-scanning approach.

        A ``ValueError`` is raised for any unrecognised statement type so that
        misconfigured fields fail loudly rather than silently falling through
        to the wrong DataFrame.
        """
        statement = getattr(field, "statement", None)

        match statement:
            case Statement.INCOME:
                return (
                    self._raw.income_stmt_q
                    if period == Period.QUARTERLY
                    else self._raw.income_stmt_a
                )
            case Statement.BALANCE_SHEET:
                return (
                    self._raw.balance_sheet_q
                    if period == Period.QUARTERLY
                    else self._raw.balance_sheet_a
                )
            case Statement.CASH_FLOW:
                return (
                    self._raw.cash_flow_q
                    if period == Period.QUARTERLY
                    else self._raw.cash_flow_a
                )
            case _:
                raise ValueError(
                    f"Field {field!r} has no recognised 'statement' attribute "
                    f"(got {statement!r}).  Ensure it is a YfFinancialField or "
                    "YfSeriesField with an explicit Statement enum value."
                )

    # Mapping from info-dict key (or sentinel string) → YfinanceParser method name.
    # Only info-dict and EPS-derived fields are routed through the parser.
    #
    # ``last_quarter_eps`` and ``last_year_eps`` use sentinel keys defined in
    # INFO_LABELS (``__last_quarter_eps__`` / ``__last_year_eps__``) so they
    # are never accidentally passed to ``ticker.info.get()``.  The parser
    # methods read from the quarterly/annual income-statement DataFrames and
    # return period-specific values distinct from the trailing ``eps_ttm``.
    _INFO_LABEL_TO_PARSER_METHOD = {
        INFO_LABELS["ticker"]:              "ticker",
        INFO_LABELS["company_name"]:        "company_name",
        INFO_LABELS["industry"]:            "industry",
        INFO_LABELS["country"]:             "country",
        INFO_LABELS["financial_currency"]:  "financial_currency",
        INFO_LABELS["trading_currency"]:    "trading_currency",
        INFO_LABELS["exchange"]:            "exchange",
        INFO_LABELS["quote_type"]:          "quote_type",
        INFO_LABELS["website"]:             "website",
        INFO_LABELS["current_price"]:       "current_price",
        INFO_LABELS["shares_outstanding"]:  "shares_outstanding",
        INFO_LABELS["market_cap"]:          "market_cap",
        INFO_LABELS["beta"]:                "beta",
        INFO_LABELS["eps_ttm"]:             "eps_ttm",
        INFO_LABELS["pe_ttm"]:              "pe_ttm",
        INFO_LABELS["last_quarter_eps"]:    "last_quarter_eps",
        INFO_LABELS["last_year_eps"]:       "last_year_eps",
        INFO_LABELS["low_52_week"]:         "low_52_week",
        INFO_LABELS["high_52_week"]:        "high_52_week",
        INFO_LABELS["fifty_day_avg"]:       "fifty_day_avg",
        INFO_LABELS["two_hundred_day_avg"]: "two_hundred_day_avg",
        INFO_LABELS["volume"]:              "volume",
        INFO_LABELS["avg_volume"]:          "avg_volume",
    }