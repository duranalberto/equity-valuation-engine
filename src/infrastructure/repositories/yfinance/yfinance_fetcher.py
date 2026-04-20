from __future__ import annotations

import logging
from typing import List, Optional, Union

from .dataframe_utils import get_series
from .value_objects import RawTickerData

logger = logging.getLogger(__name__)


class YfinanceFetcher:
    """
    Thin facade over ``RawTickerData`` providing typed accessors used by
    ``YfinanceParser``.

    Scope
    -----
    This class covers three concerns:

    * **Info-dict access** — ``get_info`` and ``get_fast_info`` for fields
      sourced from ``ticker.info`` / ``ticker.fast_info``.

    * **Annual net-income series** — ``income_series_annual`` is the single
      statement accessor retained here because ``YfinanceParser.eps_history``
      needs it to build the per-year EPS series used in ``Valuation.build``.

    * **Price series** — ``price_series`` and ``highest_price`` for historical
      price data.

    All other statement data (income, balance sheet, cash flow) is accessed
    directly from ``RawTickerData`` by ``YfinanceDataLoader`` via
    ``dataframe_utils``, so no additional statement accessors are needed here.
    """

    def __init__(self, raw: RawTickerData) -> None:
        self._raw = raw


    def get_info(self, key: str, default=None):
        if not self._raw.info:
            return default
        return self._raw.info.get(key, default)

    def get_fast_info(self, key: str, default=None):
        if self._raw.fast_info is None:
            return default
        return getattr(self._raw.fast_info, key, default)


    def income_series_annual(
        self,
        label: Union[str, List[str]],
    ) -> Optional[List[float]]:
        return get_series(self._raw.income_stmt_a, label, ascending=True)


    def price_series(self) -> Optional[List[float]]:
        history = self._raw.history
        if history is None or history.empty or "Close" not in history.columns:
            return None
        values = [
            float(v) for v in history["Close"].dropna().tolist()
            if v is not None
        ]
        return values if values else None

    def highest_price(self) -> Optional[float]:
        series = self.price_series()
        if not series:
            return None
        return max(series)