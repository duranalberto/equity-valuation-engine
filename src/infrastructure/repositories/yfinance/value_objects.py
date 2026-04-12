"""
Typed value objects for the yfinance infrastructure layer.

These replace stringly-typed dicts and bare primitives that previously
leaked internal structure into consumers.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class DataQuality(Enum):
    """
    Describes how a derived data point was obtained.

    Used by YfinanceDataLoader to signal which EPS/earnings fallback
    path was taken, so callers (MetricsLoader, validators) can adjust
    confidence levels or log warnings accordingly.

    Design 8: replaces the previous silent fallback chain in
    ``_extract_earnings_history`` where callers had no visibility into
    whether data came from the primary source or a computed approximation.
    """
    DIRECT = "direct"
    """Value came from the primary data source (ticker.earnings_history)."""

    DERIVED_FROM_STATEMENT = "derived_from_statement"
    """Value was read from a quarterly income-statement EPS row."""

    DERIVED_FROM_NET_INCOME = "derived_from_net_income"
    """Value was approximated as Net Income / Shares Outstanding."""

    MISSING = "missing"
    """No usable data was found via any path."""


@dataclass(frozen=True)
class PriceHistory:
    """
    Holds processed price history for a ticker.

    Design 7: replaces ``Optional[Dict[str, Any]]`` with keys "prices" and
    "highest".  The previous raw-dict shape required string-keyed access
    (``self._price_history.get("highest")``) with no type safety.  A frozen
    dataclass provides attribute access, IDE completion, and makes the
    contract explicit.

    Attributes:
        prices:  Monthly closing prices in USD, oldest first.
        highest: The single highest closing price in the series.
    """
    prices: List[float]
    highest: float

    @classmethod
    def from_series(cls, prices: List[float]) -> "PriceHistory":
        """
        Build a PriceHistory from a non-empty list of prices.

        Raises ValueError when the list is empty so callers cannot
        accidentally construct a PriceHistory with no data.
        """
        if not prices:
            raise ValueError("Cannot build PriceHistory from an empty price list.")
        return cls(prices=prices, highest=max(prices))


@dataclass(frozen=True)
class EarningsHistory:
    """
    Holds processed EPS history with provenance metadata.

    Design 8: previously ``_extract_earnings_history`` returned a bare
    DataFrame with no indication of which fallback path produced it.
    This dataclass pairs the values with a ``DataQuality`` tag so
    downstream code can log, warn, or skip based on data provenance.

    Attributes:
        eps_values:  Per-share earnings values, oldest first.
        quality:     How the values were obtained (see ``DataQuality``).
    """
    eps_values: List[float]
    quality: DataQuality