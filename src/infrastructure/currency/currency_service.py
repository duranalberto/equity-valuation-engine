import logging
import time
from typing import Dict, Optional

import requests

logger = logging.getLogger(__name__)

USD = "USD"

FALLBACK_FX_RATES: Dict[str, float] = {
    "EUR": 1.08, "JPY": 0.0066, "GBP": 1.25, "CAD": 0.74, "AUD": 0.66,
    "NZD": 0.61, "CHF": 1.14, "CNY": 0.14, "HKD": 0.13, "SGD": 0.74,
    "SEK": 0.093, "NOK": 0.094, "DKK": 0.145, "MXN": 0.058, "BRL": 0.20,
    "INR": 0.012, "RUB": 0.011, "ZAR": 0.055, "TRY": 0.031, "KRW": 0.00075,
    "TWD": 0.031, "PLN": 0.25, "CZK": 0.044, "HUF": 0.0030, "ILS": 0.27,
    "SAR": 0.27, "AED": 0.27,
}

_RATE_CACHE: Dict[str, tuple] = {}
CACHE_TTL = 86400
_SESSION = requests.Session()


def _get_cached_rate(currency: str) -> Optional[float]:
    entry = _RATE_CACHE.get(currency)
    if not entry:
        return None
    rate, ts = entry
    if time.time() - ts < CACHE_TTL:
        return rate
    return None


def _store_cached_rate(currency: str, rate: float) -> None:
    _RATE_CACHE[currency] = (rate, time.time())


def get_rate_to_usd(currency: str) -> float:
    if not currency:
        logger.warning("Empty or None currency received, defaulting to USD rate 1.0")
        return 1.0

    src = currency.strip().upper()
    if src == USD:
        return 1.0

    cached = _get_cached_rate(src)
    if cached is not None:
        return cached

    url = f"https://api.exchangerate.host/latest?base={USD}&symbols={src}"
    try:
        response = _SESSION.get(url, timeout=5)
        response.raise_for_status()
        data = response.json() or {}
        rates = data.get("rates") or {}
        raw_rate = rates.get(src)

        if isinstance(raw_rate, (float, int)) and raw_rate > 0:
            rate = 1.0 / raw_rate
            _store_cached_rate(src, rate)
            return rate
        else:
            logger.warning("Received invalid FX rate for %s: %s", src, raw_rate)
    except Exception as exc:
        logger.warning("FX API failure for %s: %s", src, exc)

    fallback = FALLBACK_FX_RATES.get(src)
    if fallback is None:
        logger.warning("No fallback FX rate found for currency %s; defaulting to 1.0", src)
        fallback = 1.0

    logger.warning("Using fallback FX rate for %s: %.6f", src, fallback)
    _store_cached_rate(src, fallback)
    return fallback
