from __future__ import annotations

from typing import Optional

from domain.core.enums.sectors import Sectors

_YAHOO_SECTOR_MAP = {
    "Basic Materials":        Sectors.BASIC_MATERIALS,
    "Communication Services": Sectors.COMMUNICATION_SERVICES,
    "Consumer Cyclical":      Sectors.CONSUMER_CYCLICAL,
    "Consumer Defensive":     Sectors.CONSUMER_DEFENSIVE,
    "Energy":                 Sectors.ENERGY,
    "Financial Services":     Sectors.FINANCIAL_SERVICES,
    "Healthcare":             Sectors.HEALTHCARE,
    "Industrials":            Sectors.INDUSTRIALS,
    "Real Estate":            Sectors.REAL_ESTATE,
    "Technology":             Sectors.TECHNOLOGY,
    "Utilities":              Sectors.UTILITIES,
}


def map_sector(raw_value: Optional[str]) -> Optional[Sectors]:
    """
    Convert a Yahoo Finance sector string to the ``Sectors`` enum member.

    Returns ``None`` when the value is absent or unrecognised so that callers
    can handle the miss gracefully.
    """
    if not raw_value:
        return None
    return _YAHOO_SECTOR_MAP.get(raw_value)
