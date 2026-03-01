import warnings
import pandas as pd
import yfinance as yf
from typing import Optional, Dict, Any, List, cast
from infrastructure.repositories.financial_repository import (
    Period, Statement, FinancialRepository,
    BaseField, EnumField, FinancialField, LabelField
)
from infrastructure.mappers.stock_metrics_mapper import BaseStockMetricsMapper
from infrastructure.currency import get_rate_to_usd
from .mappers import (
    StockMetricsMapper, sector_mapper, CurrencyType, CurrencyField,
    YfFinancialField, YfLabelField,
    FINANCIAL_CURRENCY_LABEL, TRADING_CURRENCY_LABEL, SECTOR_LABEL
)
from .dataframe_utils import (
    extract_from_dataframe, normalize_df_index,
    extract_sorted_numeric_column, get_ordered_numeric_series,
    calculate_ttm_from_series
)


class YfinanceDataLoader(FinancialRepository):
    mapper: BaseStockMetricsMapper 
    
    def __init__(self, ticker_symbol: str):
        self.ticker_symbol = str(ticker_symbol).strip().upper()
        if not self.ticker_symbol:
            raise ValueError("Ticker symbol is required")
        
        self.mapper = StockMetricsMapper()
        self._history_cache: Dict[str, pd.DataFrame] = {}
        
        ticker = yf.Ticker(self.ticker_symbol)
        self.info = ticker.info if isinstance(ticker.info , dict) else {}
        
        fin_currency_code = self.info.get(FINANCIAL_CURRENCY_LABEL)
        trade_currency_code = self.info.get(TRADING_CURRENCY_LABEL)
        self._financial_rate = get_rate_to_usd(fin_currency_code)
        self._trading_rate = get_rate_to_usd(trade_currency_code)
        
        self._financials = self._extract_financials(ticker)
        self._earnings_history = self._extract_earnings_history(ticker)
        self._price_history = self._extract_price_history(ticker)
        self._eps_history = self._extract_eps_history()
        

    def debug_financial_coverage(self) -> Dict[str, Any]:
        debug_info = {}

        for period, stmts in self._financials.items():
            p_key = str(period.value)
            debug_info[p_key] = {}

            for stmt_type, df in stmts.items():
                s_key = str(stmt_type.value)

                if df.empty:
                    debug_info[p_key][s_key] = {
                        "available_fields": {},
                        "total_fields": 0,
                        "empty": True
                    }
                    continue

                field_info = {}
                for idx in df.index:
                    row = df.loc[idx]
                    numeric = pd.to_numeric(row, errors="coerce")
                    count = numeric.count()

                    field_info[str(idx)] = {
                        "values_available": int(count),
                        "has_ttm_coverage": (
                            count >= 4 if period == Period.QUARTERLY else None
                        )
                    }

                debug_info[p_key][s_key] = {
                    "available_fields": field_info,
                    "total_fields": len(field_info),
                    "empty": False
                }

        return debug_info
    
    def _get_rate(self, field: CurrencyField) -> float:
        match field.currency_type:
            case CurrencyType.FINANCIAL:
                return self._financial_rate
            case CurrencyType.TRADING:
                return self._trading_rate
        return 1.0
    
    def _extract_financials(self, ticker: yf.Ticker):
        def safe_df(x):
            try:
                if x is None:
                    return pd.DataFrame()
                return x if isinstance(x, pd.DataFrame) else pd.DataFrame(x)
            except Exception as exc:
                warnings.warn(
                    f"safe_df failed for {self.ticker_symbol}: "
                    f"{type(exc).__name__}"
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
    

    def _extract_earnings_history(self, ticker: yf.Ticker) -> pd.DataFrame:
        raw = getattr(ticker, "earnings_history", None)
        df = pd.DataFrame()
        rate = self._financial_rate

        if isinstance(raw, list):
            df = pd.DataFrame(raw)
        elif isinstance(raw, pd.DataFrame):
            df = raw.copy()

        if not df.empty and "epsActual" in df.columns:
            df["epsActual"] = pd.to_numeric(df["epsActual"], errors="coerce") * rate
            return df
        
        q_income = self._get_statement_df(Period.QUARTERLY, Statement.INCOME)
        
        eps_labels = [
            "diluted eps", "eps", "epsactual",
            "diluted earnings per share", "earnings per share"
        ]
        
        eps_series = get_ordered_numeric_series(q_income, eps_labels)
        
        if eps_series is not None:
            return pd.DataFrame({"epsActual": eps_series * rate})
        
        earnings_series = extract_from_dataframe(
            normalize_df_index(q_income),
            ["earnings", "net income", "netincome"],
            from_index=True
        )
        if earnings_series is not None:
            earnings_vals = pd.to_numeric(earnings_series, errors="coerce").dropna()
            if not earnings_vals.empty:
                earnings_usd = earnings_vals * rate
                shares = self.info.get("sharesOutstanding") or self.info.get("sharesDiluted")
                if shares and isinstance(shares, (int, float)) and shares > 0:
                    eps_calc = earnings_usd / float(shares)
                    return pd.DataFrame({"epsActual": eps_calc})

        return pd.DataFrame()

    def _extract_price_history(self, ticker: yf.Ticker) -> Optional[Dict[str, Any]]:
        try:
            df = self._history_cached(ticker, period="max", interval="1mo")
        except Exception:
            return None

        if df.empty:
            return None
        
        candidate_cols = ["Adj Close", "Close"]
        
        price_series = None
        for col in candidate_cols:
            if col in df.columns:
                price_series = pd.to_numeric(df[col], errors='coerce').dropna()
                break
        
        if price_series is None or price_series.empty:
            return None

        rate = self._trading_rate
        converted = (price_series * rate).tolist()

        return {
            "prices": converted,
            "highest": max(converted) if converted else None
        }

    def _extract_eps_history(self) -> Optional[List[float]]:
        if self._earnings_history.empty:
            return None

        df = self._earnings_history

        vals = extract_sorted_numeric_column(
            df=df,
            date_col="endDate",
            numeric_candidates=["epsActual"]
        )

        return [float(v) for v in vals] if vals else None

    def _history_cached(self, ticker: yf.Ticker, period="max", interval="1mo") -> pd.DataFrame:
        key = f"{self.ticker_symbol}:{period}:{interval}"
        cached = self._history_cache.get(key)

        if cached is not None:
            return cached

        df = ticker.history(period=period, interval=interval)
        if isinstance(df, pd.DataFrame) and not df.empty:
            self._history_cache[key] = df

        return df

    def _get_statement_df(self, period: Period, stmt: Statement) -> pd.DataFrame:
        df = self._financials.get(period, {}).get(stmt)
        return df if isinstance(df, pd.DataFrame) else pd.DataFrame()

    def get_label(self, field: BaseField) -> Optional[Any]:
        
        if isinstance(field, EnumField):
            value = self.info.get(field.label)
            if(field.label == SECTOR_LABEL) and isinstance(value, str):
                normalized_value = value.lower().replace(" ", "-")
                return sector_mapper.get_key_from_value(normalized_value)
            return value

        if isinstance(field, LabelField):
            currency_type = getattr(field, 'currency_type', None)
            
            for label_str in field.label.split(","):
                yf_label_field = YfLabelField(
                    label=label_str.strip(),
                    currency_type=currency_type
                )
                
                value = self.info.get(yf_label_field.label)
                
                if value is not None:
                    if isinstance(field, CurrencyField):
                        currency_field = cast(CurrencyField, field)
                        if isinstance(value, (int, float)):
                            return value * self._get_rate(currency_field)
                    return value
            return None
        return None

    def get_ttm_from_quarters(self, field: FinancialField, year_offset=0) -> Optional[float]:
        yf_field = cast(YfFinancialField, field)

        if year_offset < 0:
            raise ValueError("year_offset cannot be negative")

        df = self._get_statement_df(Period.QUARTERLY, yf_field.statement)
        q_vals_series = get_ordered_numeric_series(df, yf_field.label)
        if q_vals_series is None:
            return None

        ttm_sum = calculate_ttm_from_series(q_vals_series, year_offset)
        if ttm_sum is None:
            return None
        
        return ttm_sum * self._get_rate(cast(CurrencyField, yf_field))

    def get_annual_value(self, field: FinancialField, year_offset=0) -> Optional[float]:
        yf_field = cast(YfFinancialField, field)

        if year_offset < 0:
            raise ValueError("year_offset cannot be negative")

        df = self._get_statement_df(Period.ANNUAL, yf_field.statement)
        annual_vals = get_ordered_numeric_series(df, yf_field.label)
        if annual_vals is None or len(annual_vals) <= year_offset:
            return None

        val_num = float(annual_vals.iloc[year_offset])
        return val_num * self._get_rate(cast(CurrencyField, yf_field))

    def get_latest_numeric(self, field: FinancialField) -> Optional[float]:
        yf_field = cast(YfFinancialField, field)

        df = self._get_statement_df(yf_field.period, yf_field.statement)
        numeric = get_ordered_numeric_series(df, yf_field.label)
        if numeric is None:
            return None

        raw_val = float(numeric.iloc[0])
        return raw_val * self._get_rate(cast(CurrencyField, yf_field))

    def get_highest_price(self) -> Optional[float]:
        return self._price_history.get("highest") if self._price_history else None

    def get_price_history(self) -> Optional[List[float]]:
        return self._price_history.get("prices") if self._price_history else None

    def get_eps_history(self) -> Optional[List[float]]:
        return self._eps_history