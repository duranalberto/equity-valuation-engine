import hashlib
import logging
import math
import random
from datetime import date
from typing import Dict, List, Optional

from config.config_loader import load_valuation_config
from domain.metrics.stock import StockMetrics

logger = logging.getLogger(__name__)

_scenarios_cfg = load_valuation_config("scenarios")

_GROWTH_FLOOR    = -0.20
_GROWTH_CEILING  =  0.50
_FALLBACK_BASE_GROWTH = 0.04


def _default_seed(ticker: str) -> int:
    """
    Derive a stable integer seed from the ticker symbol and the current
    calendar date (YYYY-MM-DD).

    This ensures:
    - The same ticker on the same day always yields identical growth rates.
    - Results change naturally on a new calendar day (avoids stale-cache
      artefacts while keeping intra-day runs perfectly reproducible).
    - Different tickers on the same day never collide.
    """
    key    = f"{ticker.upper()}:{date.today().isoformat()}"
    digest = hashlib.sha256(key.encode()).hexdigest()
    return int(digest[:16], 16)


def _derive_base_growth(stock_metrics: StockMetrics) -> float:
    val = stock_metrics.valuation
    fin = stock_metrics.financials

    candidates: List[float] = []

    if val and val.forward_growth_rate is not None and val.forward_growth_rate != 0.0:
        candidates.append(val.forward_growth_rate)
    if val and val.fcf_cagr is not None and isinstance(val.fcf_cagr, (int, float)) and math.isfinite(val.fcf_cagr):
        candidates.append(val.fcf_cagr)
    if fin and fin.net_income_growth is not None:
        candidates.append(fin.net_income_growth)
    if fin and fin.revenue_growth_rate is not None:
        candidates.append(fin.revenue_growth_rate)

    if not candidates:
        logger.debug(
            "No stock-specific growth signal found for %s; using fallback %.0f%%.",
            stock_metrics.profile.ticker, _FALLBACK_BASE_GROWTH * 100,
        )
        return _FALLBACK_BASE_GROWTH

    candidates = [c for c in candidates if isinstance(c, (int, float)) and math.isfinite(c)]
    if not candidates:
        logger.debug(
            "No finite stock-specific growth signal found for %s; using fallback %.0f%%.",
            stock_metrics.profile.ticker, _FALLBACK_BASE_GROWTH * 100,
        )
        return _FALLBACK_BASE_GROWTH

    base    = sum(candidates) / len(candidates)
    clamped = max(_GROWTH_FLOOR, min(_GROWTH_CEILING, base))
    if clamped != base:
        logger.debug(
            "Base growth for %s clamped from %.2f%% to %.2f%%.",
            stock_metrics.profile.ticker, base * 100, clamped * 100,
        )
    return clamped


def generate_growth_scenarios(
    stock_metrics: StockMetrics,
    projection_years: int,
    margin_of_safety: float = 0.25,
    random_seed: Optional[int] = None,
    stochastic: bool = False,
) -> Dict[str, List[float]]:
    """
    Generate Bear / Base / Bull growth-rate lists for a given ticker.

    Scenario multipliers and volatility bands are loaded from
    ``config/valuations/scenarios.yaml`` rather than being hardcoded.

    Reproducibility
    ---------------
    By default (``stochastic=False``) the seed is deterministically derived
    from the ticker symbol and today's date via :func:`_default_seed`.

    Pass ``stochastic=True`` (and optionally an explicit ``random_seed``) to
    opt into non-deterministic mode, e.g. for Monte Carlo simulations.
    """
    if random_seed is not None:
        seed = random_seed
    elif stochastic:
        seed = None
    else:
        seed = _default_seed(stock_metrics.profile.ticker)

    rng    = random.Random(seed)
    sector = stock_metrics.profile.sector
    base_growth = _derive_base_growth(stock_metrics)

    scenarios: Dict[str, List[float]] = {}
    for scenario_name in ("Bear", "Base", "Bull"):
        multiplier = _scenarios_cfg.get_nested_float(
            "scenario_multipliers", scenario_name, sector, default=1.0
        )
        volatility = _scenarios_cfg.get_nested_float(
            "scenario_volatility", scenario_name, sector, default=0.005
        )

        if scenario_name == "Bear":
            multiplier *= (1.0 - margin_of_safety)
        elif scenario_name == "Bull":
            multiplier *= (1.0 + margin_of_safety)

        growth_list: List[float] = []
        for _ in range(projection_years):
            noise = rng.uniform(-volatility, volatility)
            raw   = base_growth * multiplier + noise
            growth_list.append(max(_GROWTH_FLOOR, min(_GROWTH_CEILING, raw)))

        scenarios[scenario_name] = growth_list

    return scenarios


def evaluate_price(
    current_price: float,
    intrinsic_value: float,
    margin: float = 0.2,
) -> str:
    lower = intrinsic_value * (1 - margin)
    upper = intrinsic_value * (1 + margin)
    if current_price < lower:
        return "undervalued"
    if current_price > upper:
        return "overvalued"
    return "reasonable"