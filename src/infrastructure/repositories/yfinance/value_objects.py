from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class DataQuality(Enum):
    DIRECT = "direct"
    DERIVED_FROM_STATEMENT = "derived_from_statement"
    DERIVED_FROM_NET_INCOME = "derived_from_net_income"
    MISSING = "missing"


@dataclass(frozen=True)
class PriceHistory:
    prices: List[float]
    highest: float

    @classmethod
    def from_series(cls, prices: List[float]) -> "PriceHistory":
        if not prices:
            raise ValueError("Cannot build PriceHistory from an empty price list.")
        return cls(prices=prices, highest=max(prices))


@dataclass(frozen=True)
class EarningsHistory:
    eps_values: List[float]
    quality: DataQuality
