"""
YfinanceParser — the parsing/transformation half of the old YfinanceDataLoader.

Responsibilities
----------------
* Accept a ``RawTickerData`` (produced by ``YfinanceFetcher`` or a test fixture).
* Normalise all six statement DataFrames exactly once at construction.
* Implement the full ``FinancialRepository`` protocol.
* Apply FX conversion where appropriate.
* Never call ``yf.Ticker`` or any network API.

Testing
-------
Construct with ``RawTickerData`` built from fixture DataFrames:

    raw = empty_raw("AAPL")
    # override relevant DataFrames ...
    parser = YfinanceParser(raw)
    result = parser.get_ttm_from_quarters(some_field)
    assert result == expected

No mocking required — the parser is a pure function of its input.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, cast

import pandas as pd

from infrastructure.repositories.financial_repository import (
    BaseField, EnumField, FinancialField, FinancialRepository,
    LabelField, Period, Statement,
)
from infrastructure.mappers.stock_metrics_mapper import BaseStockMetricsMapper
from infrastructure.currency import get_rate_to_usd

from .mappers import (
    StockMetricsMapper,
    sector_mapper,
    CurrencyType,
    CurrencyField,
    YfFinancialField,
    YfLabelField,
    FINANCIAL_CURRENCY_LABEL,
    TRADING_CURRENCY_LABEL,
    SECTOR_LABEL,
)
from .dataframe_utils import (
    normalize_df_index,
    get_ordered_numeric_series,
    calculate_ttm_from_series,
)
from .raw_ticker_data import RawTickerData
from .value_objects import DataQuality, EarningsHistory, PriceHistory

logger = logging.getLogger(__name__)


class YfinanceParser:
    """
    Parse a ``RawTickerData`` and expose it through ``FinancialRepository``.

    All six statement DataFrames are normalised once in ``__init__``.
    Every subsequent lookup operates on the cached, normalised copies —
    no repeated normalisation per field access.
    """

    mapper: BaseStockMetricsMapper

    def __init__(self, raw: RawTickerData) -> None:
        if not isinstance(raw, RawTickerData):
            raise TypeError(
                f"YfinanceParser requires a RawTickerData, got {type(raw).__name__}"
            )

        self._raw = raw
        self.mapper = StockMetricsMapper()

        fin_currency = raw.info.get(FINANCIAL_CURRENCY_LABEL)
        trade_currency = raw.info.get(TRADING_CURRENCY_LABEL)
        self._financial_rate: float = get_rate_to_usd(fin_currency)
        self._trading_rate: float = get_rate_to_usd(trade_currency)

        self._financials: Dict[Period, Dict[Statement, pd.DataFrame]] = {
            Period.ANNUAL: {
                Statement.INCOME: self._norm(raw.annual_income),
                Statement.CASHFLOW: self._norm(raw.annual_cashflow),
                Statement.BALANCE_SHEET: self._norm(raw.annual_balance_sheet),
            },
            Period.QUARTERLY: {
                Statement.INCOME: self._norm(raw.quarterly_income),
                Statement.CASHFLOW: self._norm(raw.quarterly_cashflow),
                Statement.BALANCE_SHEET: self._norm(raw.quarterly_balance_sheet),
            },
        }

        self._earnings: EarningsHistory = self._build_earnings_history()
        self._price_history: Optional[PriceHistory] = self._build_price_history()

        self._eps_quality: DataQuality = self._earnings.quality
        self._eps_history: Optional[List[float]] = (
            self._earnings.eps_values or None
        )

    def get_label(self, field: BaseField) -> Optional[Any]:
        if isinstance(field, EnumField):
            value = self._raw.info.get(field.label)
            if field.label == SECTOR_LABEL and isinstance(value, str):
                normalised = value.lower().replace(" ", "-")
                return sector_mapper.get_key_from_value(normalised)
            return value

        if isinstance(field, LabelField):
            yf_field = cast(YfLabelField, field)
            for label_str in yf_field.labels:
                value = self._raw.info.get(label_str)
                if value is not None:
                    if isinstance(yf_field, CurrencyField):
                        if isinstance(value, (int, float)):
                            return value * self._get_rate(yf_field)
                    return value
            return None

        return None

    def get_ttm_from_quarters(
        self, field: FinancialField, year_offset: int = 0
    ) -> Optional[float]:
        if year_offset < 0:
            raise ValueError("year_offset cannot be negative.")
        yf_field = cast(YfFinancialField, field)
        df = self._get_stmt(Period.QUARTERLY, yf_field.statement)
        series = get_ordered_numeric_series(df, yf_field.label)
        if series is None:
            return None
        ttm = calculate_ttm_from_series(series, year_offset)
        if ttm is None:
            return None
        return ttm * self._get_rate(cast(CurrencyField, yf_field))

    def get_annual_value(
        self, field: FinancialField, year_offset: int = 0
    ) -> Optional[float]:
        if year_offset < 0:
            raise ValueError("year_offset cannot be negative.")
        yf_field = cast(YfFinancialField, field)
        df = self._get_stmt(Period.ANNUAL, yf_field.statement)
        series = get_ordered_numeric_series(df, yf_field.label)
        if series is None or len(series) <= year_offset:
            return None
        return float(series.iloc[year_offset]) * self._get_rate(
            cast(CurrencyField, yf_field)
        )

    def get_latest_numeric(self, field: FinancialField) -> Optional[float]:
        yf_field = cast(YfFinancialField, field)
        period = yf_field.period if yf_field.period is not None else Period.QUARTERLY
        df = self._get_stmt(period, yf_field.statement)
        series = get_ordered_numeric_series(df, yf_field.label)
        if series is None:
            return None
        return float(series.iloc[0]) * self._get_rate(cast(CurrencyField, yf_field))

    def get_highest_price(self) -> Optional[float]:
        return self._price_history.highest if self._price_history else None

    def get_price_history(self) -> Optional[List[float]]:
        return self._price_history.prices if self._price_history else None

    def get_eps_history(self) -> Optional[List[float]]:
        return self._eps_history

    def get_eps_data_quality(self) -> DataQuality:
        """Expose the data-quality tag for the EPS series."""
        return self._eps_quality

    def debug_financial_coverage(self) -> Dict[str, Any]:
        debug_info: Dict[str, Any] = {}
        for period, stmts in self._financials.items():
            p_key = str(period.value)
            debug_info[p_key] = {}
            for stmt_type, df in stmts.items():
                s_key = str(stmt_type.value)
                if df.empty:
                    debug_info[p_key][s_key] = {
                        "available_fields": {},
                        "total_fields": 0,
                        "empty": True,
                    }
                    continue
                field_info = {}
                for idx in df.index:
                    row = df.loc[idx]
                    numeric = pd.to_numeric(row, errors="coerce")
                    count = int(numeric.count())
                    field_info[str(idx)] = {
                        "values_available": count,
                        "has_ttm_coverage": (
                            count >= 4 if period == Period.QUARTERLY else None
                        ),
                    }
                debug_info[p_key][s_key] = {
                    "available_fields": field_info,
                    "total_fields": len(field_info),
                    "empty": False,
                }
        return debug_info

    @staticmethod
    def _norm(df: pd.DataFrame) -> pd.DataFrame:
        """Normalise a DataFrame's index; return an empty DF if input is empty."""
        if df is None or df.empty:
            return pd.DataFrame()
        return normalize_df_index(df)

    def _get_stmt(self, period: Period, stmt: Statement) -> pd.DataFrame:
        """Return the pre-normalised DataFrame for a period/statement pair."""
        df = self._financials.get(period, {}).get(stmt)
        return df if isinstance(df, pd.DataFrame) else pd.DataFrame()

    def _get_rate(self, field: CurrencyField) -> float:
        match field.currency_type:
            case CurrencyType.FINANCIAL:
                return self._financial_rate
            case CurrencyType.TRADING:
                return self._trading_rate
        return 1.0

    def _build_earnings_history(self) -> EarningsHistory:
        """
        Build EPS history from the best available source.

        Priority order
        --------------
        1. ``earnings_history_raw`` — direct epsActual column.
        2. EPS row in the quarterly income statement.
        3. Net Income / Shares Outstanding (approximation, NO FX applied —
           the series is already in the financial currency; dividing by shares
           gives per-share values in that currency, consistent with paths 1&2).

        Design note: EPS is a per-share ratio — it must NOT be multiplied by
        the financial FX rate.  The original loader had an inconsistency where
        path 3 applied ``* financial_rate`` before dividing by shares; this is
        removed here.  All three paths return per-share values as-reported.
        """
        eps_labels = [
            "diluted eps", "eps", "epsactual",
            "diluted earnings per share", "earnings per share",
        ]

        raw_eh = self._raw.earnings_history_raw
        if raw_eh is not None and not raw_eh.empty and "epsActual" in raw_eh.columns:
            series = pd.to_numeric(raw_eh["epsActual"], errors="coerce").dropna()
            if not series.empty:
                logger.debug(
                    "%s: EPS from primary source (earnings_history), %d values.",
                    self._raw.ticker_symbol, len(series),
                )
                return EarningsHistory(
                    eps_values=series.tolist(),
                    quality=DataQuality.DIRECT,
                )

        q_income = self._get_stmt(Period.QUARTERLY, Statement.INCOME)
        eps_series = get_ordered_numeric_series(q_income, eps_labels)
        if eps_series is not None and not eps_series.empty:
            logger.debug(
                "%s: EPS from quarterly income statement, %d values.",
                self._raw.ticker_symbol, len(eps_series),
            )
            return EarningsHistory(
                eps_values=eps_series.tolist(),
                quality=DataQuality.DERIVED_FROM_STATEMENT,
            )

        ni_labels = ["net income", "netincome", "net_income"]
        ni_series = get_ordered_numeric_series(q_income, ni_labels)
        if ni_series is not None and not ni_series.empty:
            shares = (
                self._raw.info.get("sharesOutstanding")
                or self._raw.info.get("sharesDiluted")
            )
            if shares and isinstance(shares, (int, float)) and shares > 0:
                logger.debug(
                    "%s: EPS approximated as Net Income / Shares (%s).",
                    self._raw.ticker_symbol,
                    DataQuality.DERIVED_FROM_NET_INCOME.value,
                )
                eps_approx = ni_series / float(shares)
                return EarningsHistory(
                    eps_values=eps_approx.tolist(),
                    quality=DataQuality.DERIVED_FROM_NET_INCOME,
                )

        logger.debug(
            "%s: No EPS data available from any source.",
            self._raw.ticker_symbol,
        )
        return EarningsHistory(eps_values=[], quality=DataQuality.MISSING)


    def _build_price_history(self) -> Optional[PriceHistory]:
        """
        Build monthly price history (USD-converted) from the raw price DataFrame.
        """
        df = self._raw.price_history_raw
        if df is None or df.empty:
            return None

        price_series = None
        for col in ("Adj Close", "Close"):
            if col in df.columns:
                price_series = pd.to_numeric(df[col], errors="coerce").dropna()
                break

        if price_series is None or price_series.empty:
            return None

        converted = (price_series * self._trading_rate).tolist()
        if not converted:
            return None

        return PriceHistory.from_series(converted)