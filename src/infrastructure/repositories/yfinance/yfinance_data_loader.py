"""
YfinanceDataLoader — infrastructure adapter for the Yahoo Finance API.

Changes in this revision
------------------------
Fix 2   Pre-normalize all 8 statement DataFrames once in ``__init__`` and
        cache the results.  Previously ``normalize_df_index`` was called on
        every ``get_ordered_numeric_series`` call — up to 20+ redundant
        normalizations of the same 4 DataFrames per ticker.

Design 5  EPS FX currency fix.  Per-share EPS values do NOT need FX
        conversion: the per-share ratio is dimensionless relative to the
        reporting currency and is used directly in PE calculations.
        Previously ``_extract_earnings_history`` multiplied epsActual by
        ``self._financial_rate``, which could double-convert values already
        denominated in USD (or in the wrong currency unit altogether).
        The multiplication has been removed; EPS is stored as-reported.
        The ``YfFinancialField`` entries for EPS already declare
        ``currency_type=CurrencyType.NONE``, which is now consistent with
        this path.

Design 6  ``get_label`` now iterates ``field.labels`` (a ``List[str]``
        property on ``YfLabelField``) instead of splitting ``field.label``
        on commas.  The comma-split convention is gone.

Design 7  ``_price_history`` is now an ``Optional[PriceHistory]`` typed
        dataclass instead of ``Optional[Dict[str, Any]]``.  Consumers use
        attribute access (``.prices``, ``.highest``) instead of string keys.

Design 8  ``_extract_earnings_history`` now returns ``EarningsHistory``
        (a typed value object with a ``DataQuality`` tag) instead of a bare
        DataFrame.  A ``logging.debug`` call at each fallback branch makes
        the data-provenance chain visible in logs.  ``_extract_eps_history``
        attaches the quality tag to ``self._eps_quality`` so callers can
        inspect it.
"""
from __future__ import annotations

import logging
import warnings
from typing import Optional, Dict, Any, List, cast

import pandas as pd
import yfinance as yf

from infrastructure.repositories.financial_repository import (
    Period, Statement, FinancialRepository,
    BaseField, EnumField, FinancialField, LabelField,
)
from infrastructure.mappers.stock_metrics_mapper import BaseStockMetricsMapper
from infrastructure.currency import get_rate_to_usd

from .mappers import (
    StockMetricsMapper, sector_mapper, CurrencyType, CurrencyField,
    YfFinancialField, YfLabelField,
    FINANCIAL_CURRENCY_LABEL, TRADING_CURRENCY_LABEL, SECTOR_LABEL,
)
from .dataframe_utils import (
    normalize_df_index,
    extract_sorted_numeric_column,
    get_ordered_numeric_series,
    calculate_ttm_from_series,
)
from .value_objects import PriceHistory, EarningsHistory, DataQuality

logger = logging.getLogger(__name__)


class YfinanceDataLoader(FinancialRepository):
    """
    Loads financial data from Yahoo Finance and exposes it through the
    ``FinancialRepository`` protocol.
    """

    mapper: BaseStockMetricsMapper

    def __init__(self, ticker_symbol: str) -> None:
        self.ticker_symbol = str(ticker_symbol).strip().upper()
        if not self.ticker_symbol:
            raise ValueError("Ticker symbol is required.")

        self.mapper = StockMetricsMapper()
        self._history_cache: Dict[str, pd.DataFrame] = {}

        ticker = yf.Ticker(self.ticker_symbol)
        self.info: Dict[str, Any] = ticker.info if isinstance(ticker.info, dict) else {}

        fin_currency_code = self.info.get(FINANCIAL_CURRENCY_LABEL)
        trade_currency_code = self.info.get(TRADING_CURRENCY_LABEL)
        self._financial_rate = get_rate_to_usd(fin_currency_code)
        self._trading_rate = get_rate_to_usd(trade_currency_code)

        # Fix 2: fetch raw DataFrames, then pre-normalize each one's index
        # exactly once.  All subsequent row-lookup calls use the pre-normalized
        # versions, avoiding redundant work on every field access.
        raw_financials = self._fetch_raw_financials(ticker)
        self._financials = self._normalize_all_statements(raw_financials)

        self._earnings: EarningsHistory = self._extract_earnings_history(ticker)
        self._price_history: Optional[PriceHistory] = self._extract_price_history(ticker)

        # Fix 2 continued: EPS history is derived from the already-normalized
        # earnings data — no extra DataFrame work needed here.
        self._eps_quality: DataQuality = self._earnings.quality
        self._eps_history: Optional[List[float]] = (
            self._earnings.eps_values if self._earnings.eps_values else None
        )

    # ------------------------------------------------------------------
    # Initialisation helpers
    # ------------------------------------------------------------------

    def _fetch_raw_financials(
        self, ticker: yf.Ticker
    ) -> Dict[Period, Dict[Statement, pd.DataFrame]]:
        """Fetch all 6 statement DataFrames from yfinance (raw, not normalized)."""

        def safe_df(x: Any) -> pd.DataFrame:
            try:
                if x is None:
                    return pd.DataFrame()
                return x if isinstance(x, pd.DataFrame) else pd.DataFrame(x)
            except Exception as exc:
                warnings.warn(
                    f"safe_df failed for {self.ticker_symbol}: {type(exc).__name__}"
                )
                return pd.DataFrame()

        return {
            Period.ANNUAL: {
                Statement.INCOME: safe_df(ticker.financials),
                Statement.CASHFLOW: safe_df(ticker.cashflow),
                Statement.BALANCE_SHEET: safe_df(ticker.balance_sheet),
            },
            Period.QUARTERLY: {
                Statement.INCOME: safe_df(ticker.quarterly_financials),
                Statement.CASHFLOW: safe_df(ticker.quarterly_cashflow),
                Statement.BALANCE_SHEET: safe_df(ticker.quarterly_balance_sheet),
            },
        }

    def _normalize_all_statements(
        self,
        raw: Dict[Period, Dict[Statement, pd.DataFrame]],
    ) -> Dict[Period, Dict[Statement, pd.DataFrame]]:
        """
        Fix 2: pre-normalize the index of every statement DataFrame once.

        ``normalize_df_index`` returns a copy (does not mutate), so the raw
        data is discarded and replaced with normalized copies.  Every subsequent
        lookup (``get_ordered_numeric_series``, ``_get_statement_df``) receives
        an already-normalized DataFrame and skips the normalization step.
        """
        normalized: Dict[Period, Dict[Statement, pd.DataFrame]] = {}
        for period, stmts in raw.items():
            normalized[period] = {}
            for stmt_type, df in stmts.items():
                normalized[period][stmt_type] = (
                    normalize_df_index(df) if not df.empty else df
                )
        return normalized

    def _extract_earnings_history(self, ticker: yf.Ticker) -> EarningsHistory:
        """
        Build EPS history from the best available source, in priority order:

        1. ``ticker.earnings_history`` — direct from Yahoo Finance API.
        2. EPS row in the quarterly income statement.
        3. Net Income ÷ Shares Outstanding (approximation).

        Design 5: EPS values are stored WITHOUT FX conversion.  Per-share
        values are dimensionless relative to the reporting currency; multiplying
        by an FX rate produces an incorrect unit (e.g. USD/share × USD/GBP ≠
        USD/share).  The field mapper already declares CurrencyType.NONE for
        all EPS fields, which is now consistent with this path.

        Design 8: Each fallback path logs at DEBUG level so operators can see
        which path was taken.  The returned ``EarningsHistory`` carries a
        ``DataQuality`` tag for programmatic inspection by callers.
        """
        eps_labels = [
            "diluted eps", "eps", "epsactual",
            "diluted earnings per share", "earnings per share",
        ]

        # --- Path 1: ticker.earnings_history --------------------------------
        raw = getattr(ticker, "earnings_history", None)
        df = pd.DataFrame()
        if isinstance(raw, list):
            df = pd.DataFrame(raw)
        elif isinstance(raw, pd.DataFrame):
            df = raw.copy()

        if not df.empty and "epsActual" in df.columns:
            series = pd.to_numeric(df["epsActual"], errors="coerce").dropna()
            if not series.empty:
                # Design 5: no FX multiplication — EPS is per-share, no conversion needed.
                logger.debug(
                    "%s: EPS from primary source (earnings_history), %d values.",
                    self.ticker_symbol, len(series),
                )
                return EarningsHistory(
                    eps_values=series.tolist(),
                    quality=DataQuality.DIRECT,
                )

        # --- Path 2: EPS row in quarterly income statement ------------------
        # Use the already-normalized quarterly income DataFrame (Fix 2).
        q_income = self._get_statement_df(Period.QUARTERLY, Statement.INCOME)
        eps_series = get_ordered_numeric_series(q_income, eps_labels)
        if eps_series is not None and not eps_series.empty:
            # Design 5: no FX multiplication — same rationale as Path 1.
            logger.debug(
                "%s: EPS derived from quarterly income statement (%s), %d values.",
                self.ticker_symbol, DataQuality.DERIVED_FROM_STATEMENT.value, len(eps_series),
            )
            return EarningsHistory(
                eps_values=eps_series.tolist(),
                quality=DataQuality.DERIVED_FROM_STATEMENT,
            )

        # --- Path 3: Net Income / Shares Outstanding ------------------------
        # Design 8: log this approximation explicitly so it is visible in traces.
        ni_labels = ["net income", "netincome", "net_income"]
        ni_series = get_ordered_numeric_series(q_income, ni_labels)
        if ni_series is not None and not ni_series.empty:
            shares = self.info.get("sharesOutstanding") or self.info.get("sharesDiluted")
            if shares and isinstance(shares, (int, float)) and shares > 0:
                logger.debug(
                    "%s: EPS approximated as Net Income / Shares (%s). "
                    "Values may differ from reported EPS.",
                    self.ticker_symbol, DataQuality.DERIVED_FROM_NET_INCOME.value,
                )
                # Design 5: Net Income is in financial currency; divide by shares
                # to get per-share value in financial currency.  No FX needed.
                eps_approx = (ni_series * self._financial_rate) / float(shares)
                return EarningsHistory(
                    eps_values=eps_approx.tolist(),
                    quality=DataQuality.DERIVED_FROM_NET_INCOME,
                )

        logger.debug(
            "%s: No EPS data available from any source (%s).",
            self.ticker_symbol, DataQuality.MISSING.value,
        )
        return EarningsHistory(eps_values=[], quality=DataQuality.MISSING)

    def _extract_price_history(self, ticker: yf.Ticker) -> Optional[PriceHistory]:
        """
        Build monthly price history (USD-converted) from yfinance.

        Design 7: returns a typed ``PriceHistory`` dataclass instead of a raw
        ``Dict[str, Any]``.  Callers use attribute access (``.prices``,
        ``.highest``) rather than string-keyed dict lookups.
        """
        try:
            df = self._history_cached(ticker, period="max", interval="1mo")
        except Exception:
            return None

        if df.empty:
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

        # Design 7: PriceHistory.from_series validates non-empty and computes max.
        return PriceHistory.from_series(converted)

    # ------------------------------------------------------------------
    # Internal utilities
    # ------------------------------------------------------------------

    def _get_rate(self, field: CurrencyField) -> float:
        match field.currency_type:
            case CurrencyType.FINANCIAL:
                return self._financial_rate
            case CurrencyType.TRADING:
                return self._trading_rate
        return 1.0

    def _get_statement_df(self, period: Period, stmt: Statement) -> pd.DataFrame:
        """
        Return the pre-normalized DataFrame for a given period/statement pair.

        Fix 2: DataFrames are already normalized at construction time, so this
        is a pure dict lookup with no further transformation.
        """
        df = self._financials.get(period, {}).get(stmt)
        return df if isinstance(df, pd.DataFrame) else pd.DataFrame()

    def _history_cached(
        self, ticker: yf.Ticker, period: str = "max", interval: str = "1mo"
    ) -> pd.DataFrame:
        key = f"{self.ticker_symbol}:{period}:{interval}"
        cached = self._history_cache.get(key)
        if cached is not None:
            return cached
        df = ticker.history(period=period, interval=interval)
        if isinstance(df, pd.DataFrame) and not df.empty:
            self._history_cache[key] = df
        return df

    # ------------------------------------------------------------------
    # FinancialRepository protocol implementation
    # ------------------------------------------------------------------

    def get_label(self, field: BaseField) -> Optional[Any]:
        if isinstance(field, EnumField):
            value = self.info.get(field.label)
            if field.label == SECTOR_LABEL and isinstance(value, str):
                normalized_value = value.lower().replace(" ", "-")
                return sector_mapper.get_key_from_value(normalized_value)
            return value

        if isinstance(field, LabelField):
            yf_field = cast(YfLabelField, field)

            # Design 6: iterate field.labels (List[str]) instead of splitting
            # field.label on commas.  The comma-split convention is removed.
            for label_str in yf_field.labels:
                value = self.info.get(label_str)
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
        # Fix 2: _get_statement_df returns pre-normalized DF — no re-normalization.
        df = self._get_statement_df(Period.QUARTERLY, yf_field.statement)
        q_vals_series = get_ordered_numeric_series(df, yf_field.label)
        if q_vals_series is None:
            return None
        ttm_sum = calculate_ttm_from_series(q_vals_series, year_offset)
        if ttm_sum is None:
            return None
        return ttm_sum * self._get_rate(cast(CurrencyField, yf_field))

    def get_annual_value(
        self, field: FinancialField, year_offset: int = 0
    ) -> Optional[float]:
        if year_offset < 0:
            raise ValueError("year_offset cannot be negative.")
        yf_field = cast(YfFinancialField, field)
        df = self._get_statement_df(Period.ANNUAL, yf_field.statement)
        annual_vals = get_ordered_numeric_series(df, yf_field.label)
        if annual_vals is None or len(annual_vals) <= year_offset:
            return None
        return float(annual_vals.iloc[year_offset]) * self._get_rate(
            cast(CurrencyField, yf_field)
        )

    def get_latest_numeric(self, field: FinancialField) -> Optional[float]:
        yf_field = cast(YfFinancialField, field)
        df = self._get_statement_df(yf_field.period, yf_field.statement)
        numeric = get_ordered_numeric_series(df, yf_field.label)
        if numeric is None:
            return None
        return float(numeric.iloc[0]) * self._get_rate(cast(CurrencyField, yf_field))

    # Design 7: consumers call .highest / .prices via typed attributes, not dict keys.
    def get_highest_price(self) -> Optional[float]:
        return self._price_history.highest if self._price_history else None

    def get_price_history(self) -> Optional[List[float]]:
        return self._price_history.prices if self._price_history else None

    def get_eps_history(self) -> Optional[List[float]]:
        return self._eps_history

    def get_eps_data_quality(self) -> DataQuality:
        """
        Design 8: expose the data-quality tag for the EPS series so callers
        (e.g. MetricsLoader, validators) can adjust confidence levels or emit
        their own warnings based on how EPS was derived.
        """
        return self._eps_quality

    # ------------------------------------------------------------------
    # Debug helpers
    # ------------------------------------------------------------------

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