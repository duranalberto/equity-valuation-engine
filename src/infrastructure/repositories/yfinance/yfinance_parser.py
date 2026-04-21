from __future__ import annotations

import logging
from typing import List, Optional

from .mappers.common_constants import INCOME_STMT_LABELS, INFO_LABELS
from .mappers.enum_mappers import map_sector
from .yfinance_fetcher import YfinanceFetcher

logger = logging.getLogger(__name__)


class YfinanceParser:
    """
    Higher-level extraction for info-dict and price/EPS data.

    BUG-9 fix: pe_ttm() now returns None when the value is absent or
    non-numeric (e.g. companies with negative EPS have no P/E ratio in
    yfinance).  MarketData.pe_ttm is typed Optional[float] to match.
    PEChecker guards all comparisons against None so no TypeError can occur.
    """

    def __init__(self, fetcher: YfinanceFetcher) -> None:
        self._f = fetcher

    def ticker(self) -> Optional[str]:
        return self._f.get_info(INFO_LABELS["ticker"])

    def company_name(self) -> Optional[str]:
        return self._f.get_info(INFO_LABELS["company_name"])

    def sector(self):
        raw = self._f.get_info(INFO_LABELS["sector"])
        return map_sector(raw) if raw else None

    def industry(self) -> Optional[str]:
        return self._f.get_info(INFO_LABELS["industry"])

    def country(self) -> Optional[str]:
        return self._f.get_info(INFO_LABELS["country"])

    def financial_currency(self) -> Optional[str]:
        return self._f.get_info(INFO_LABELS["financial_currency"])

    def trading_currency(self) -> Optional[str]:
        return self._f.get_info(INFO_LABELS["trading_currency"])

    def exchange(self) -> Optional[str]:
        return self._f.get_info(INFO_LABELS["exchange"])

    def quote_type(self) -> Optional[str]:
        return self._f.get_info(INFO_LABELS["quote_type"])

    def website(self) -> Optional[str]:
        return self._f.get_info(INFO_LABELS["website"])

    def current_price(self) -> Optional[float]:
        price = self._f.get_fast_info("last_price")
        if price is None:
            price = self._f.get_info(INFO_LABELS["current_price"])
        return float(price) if price else None

    def shares_outstanding(self) -> Optional[int]:
        raw = self._f.get_fast_info("shares")
        if raw is None:
            raw = self._f.get_info(INFO_LABELS["shares_outstanding"])
        return int(raw) if raw else None

    def market_cap(self) -> Optional[float]:
        raw = self._f.get_fast_info("market_cap")
        if raw is None:
            raw = self._f.get_info(INFO_LABELS["market_cap"])
        return float(raw) if raw else None

    def beta(self) -> Optional[float]:
        raw = self._f.get_info(INFO_LABELS["beta"])
        if raw is None:
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    def eps_ttm(self) -> Optional[float]:
        raw = self._f.get_info(INFO_LABELS["eps_ttm"])
        return float(raw) if raw is not None else None

    def last_quarter_eps(self) -> Optional[float]:
        """
        Return the most recent quarterly EPS, derived from quarterly net income
        divided by shares outstanding.
        """
        ni_series = self._f.income_series_quarterly(INCOME_STMT_LABELS["net_income"])
        shares = self.shares_outstanding()
        if not ni_series or not shares:
            return None

        from calculations.common import safe_div

        latest_net_income = ni_series[-1]
        return safe_div(latest_net_income, float(shares))

    def last_year_eps(self) -> Optional[float]:
        """
        Return the most recent annual EPS, derived from annual net income
        divided by shares outstanding.
        """
        ni_series = self._f.income_series_annual(INCOME_STMT_LABELS["net_income"])
        shares = self.shares_outstanding()
        if not ni_series or not shares:
            return None

        from calculations.common import safe_div

        latest_net_income = ni_series[-1]
        return safe_div(latest_net_income, float(shares))

    def pe_ttm(self) -> Optional[float]:
        """
        BUG-9 fix: return None (not 0.0) when P/E is absent.

        yfinance returns None for trailingPE on companies with negative or
        zero EPS (no meaningful P/E exists).  Returning 0.0 here would cause
        PEChecker._check_earnings_stability to compare 0.0 > 40 and 0.0 == 0.0,
        silently treating a missing P/E as a zero P/E.  Returning None lets the
        checker detect the absence explicitly and emit the correct factor.
        """
        raw = self._f.get_info(INFO_LABELS["pe_ttm"])
        if raw is None:
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    def low_52_week(self) -> Optional[float]:
        raw = self._f.get_fast_info("year_low")
        if raw is None:
            raw = self._f.get_info(INFO_LABELS.get("low_52_week", "fiftyTwoWeekLow"))
        return float(raw) if raw else None

    def high_52_week(self) -> Optional[float]:
        raw = self._f.get_fast_info("year_high")
        if raw is None:
            raw = self._f.get_info(INFO_LABELS.get("high_52_week", "fiftyTwoWeekHigh"))
        return float(raw) if raw else None

    def fifty_day_avg(self) -> Optional[float]:
        raw = self._f.get_info(INFO_LABELS.get("fifty_day_avg", "fiftyDayAverage"))
        return float(raw) if raw else None

    def two_hundred_day_avg(self) -> Optional[float]:
        raw = self._f.get_info(INFO_LABELS.get("two_hundred_day_avg", "twoHundredDayAverage"))
        return float(raw) if raw else None

    def volume(self) -> Optional[int]:
        raw = self._f.get_fast_info("three_month_average_volume")
        if raw is None:
            raw = self._f.get_info(INFO_LABELS.get("volume", "volume"))
        return int(raw) if raw else None

    def avg_volume(self) -> Optional[int]:
        raw = self._f.get_info(INFO_LABELS.get("avg_volume", "averageVolume"))
        return int(raw) if raw else None

    def price_history(self) -> Optional[List[float]]:
        return self._f.price_series()

    def highest_price(self) -> Optional[float]:
        return self._f.highest_price()

    def eps_history(self) -> Optional[List[float]]:
        ni_series = self._f.income_series_annual(INCOME_STMT_LABELS["net_income"])
        shares    = self.shares_outstanding()
        if not ni_series or not shares:
            return None
        from calculations.common import safe_div
        result  = [safe_div(ni, float(shares)) for ni in ni_series]
        cleaned = [v for v in result if v is not None]
        return cleaned if cleaned else None
