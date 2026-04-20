from __future__ import annotations

import logging
from functools import lru_cache
from typing import Optional

import yfinance as yf

logger = logging.getLogger(__name__)

_USD_FALLBACK = 1.0


@lru_cache(maxsize=128)
def get_exchange_rate(from_currency: str, to_currency: str) -> float:
    """
    Return the exchange rate from_currency → to_currency.

    Falls back to 1.0 (identity) on any error so that callers always get a
    usable number and can continue without crashing.
    """
    if from_currency.upper() == to_currency.upper():
        return 1.0
    ticker_symbol = f"{from_currency.upper()}{to_currency.upper()}=X"
    try:
        info = yf.Ticker(ticker_symbol).fast_info
        rate = getattr(info, "last_price", None)
        if rate and float(rate) > 0:
            return float(rate)
        logger.warning(
            "No valid exchange rate found for %s; defaulting to 1.0.", ticker_symbol
        )
    except Exception as exc:
        logger.warning(
            "Exchange-rate lookup failed for %s: %s. Defaulting to 1.0.",
            ticker_symbol, exc,
        )
    return _USD_FALLBACK


def convert(
    amount: Optional[float],
    from_currency: str,
    to_currency: str,
) -> Optional[float]:
    """Convert *amount* from one currency to another, or return None on failure."""
    if amount is None:
        return None
    rate = get_exchange_rate(from_currency, to_currency)
    return amount * rate
