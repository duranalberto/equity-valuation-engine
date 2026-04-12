import random
import logging
from typing import Dict, List, Optional
from domain.core.enums import Sectors
from domain.metrics.stock import StockMetrics

logger = logging.getLogger(__name__)


SECTOR_SCENARIO_MULTIPLIERS = {
    "Bear": {
        Sectors.BASIC_MATERIALS: 0.80,
        Sectors.COMMUNICATION_SERVICES: 0.80,
        Sectors.CONSUMER_CYCLICAL: 0.80,
        Sectors.CONSUMER_DEFENSIVE: 0.85,
        Sectors.ENERGY: 0.75,
        Sectors.FINANCIAL_SERVICES: 0.80,
        Sectors.HEALTHCARE: 0.85,
        Sectors.INDUSTRIALS: 0.80,
        Sectors.REAL_ESTATE: 0.80,
        Sectors.TECHNOLOGY: 0.80,
        Sectors.UTILITIES: 0.85,
    },
    "Base": {s: 1.0 for s in Sectors},
    "Bull": {
        Sectors.BASIC_MATERIALS: 1.20,
        Sectors.COMMUNICATION_SERVICES: 1.20,
        Sectors.CONSUMER_CYCLICAL: 1.20,
        Sectors.CONSUMER_DEFENSIVE: 1.15,
        Sectors.ENERGY: 1.20,
        Sectors.FINANCIAL_SERVICES: 1.20,
        Sectors.HEALTHCARE: 1.15,
        Sectors.INDUSTRIALS: 1.20,
        Sectors.REAL_ESTATE: 1.15,
        Sectors.TECHNOLOGY: 1.20,
        Sectors.UTILITIES: 1.10,
    },
}

SECTOR_VOLATILITY = {
    "Bear": {
        Sectors.BASIC_MATERIALS: 0.010,
        Sectors.COMMUNICATION_SERVICES: 0.010,
        Sectors.CONSUMER_CYCLICAL: 0.015,
        Sectors.CONSUMER_DEFENSIVE: 0.010,
        Sectors.ENERGY: 0.015,
        Sectors.FINANCIAL_SERVICES: 0.010,
        Sectors.HEALTHCARE: 0.010,
        Sectors.INDUSTRIALS: 0.010,
        Sectors.REAL_ESTATE: 0.010,
        Sectors.TECHNOLOGY: 0.020,
        Sectors.UTILITIES: 0.010,
    },
    "Base": {
        Sectors.BASIC_MATERIALS: 0.005,
        Sectors.COMMUNICATION_SERVICES: 0.005,
        Sectors.CONSUMER_CYCLICAL: 0.005,
        Sectors.CONSUMER_DEFENSIVE: 0.005,
        Sectors.ENERGY: 0.007,
        Sectors.FINANCIAL_SERVICES: 0.005,
        Sectors.HEALTHCARE: 0.005,
        Sectors.INDUSTRIALS: 0.005,
        Sectors.REAL_ESTATE: 0.005,
        Sectors.TECHNOLOGY: 0.010,
        Sectors.UTILITIES: 0.003,
    },
    "Bull": {
        Sectors.BASIC_MATERIALS: 0.020,
        Sectors.COMMUNICATION_SERVICES: 0.020,
        Sectors.CONSUMER_CYCLICAL: 0.020,
        Sectors.CONSUMER_DEFENSIVE: 0.015,
        Sectors.ENERGY: 0.020,
        Sectors.FINANCIAL_SERVICES: 0.020,
        Sectors.HEALTHCARE: 0.015,
        Sectors.INDUSTRIALS: 0.020,
        Sectors.REAL_ESTATE: 0.015,
        Sectors.TECHNOLOGY: 0.025,
        Sectors.UTILITIES: 0.010,
    },
}

_GROWTH_FLOOR = -0.20   # −20 %
_GROWTH_CEILING = 0.50  #  +50 %
_FALLBACK_BASE_GROWTH = 0.04


def _derive_base_growth(stock_metrics: StockMetrics) -> float:
    """
    Derive a stock-specific base growth rate from available metrics,
    in priority order:

    1. Historical EPS CAGR (most direct earnings-growth signal).
    2. FCF CAGR (free-cash-flow momentum).
    3. Net income growth rate (TTM over prior TTM).
    4. Revenue growth rate (top-line proxy when bottom-line is noisy).
    5. Sector fallback of 4% if nothing meaningful is available.

    All candidates are clamped to [_GROWTH_FLOOR, _GROWTH_CEILING] before use.
    """
    val = stock_metrics.valuation
    fin = stock_metrics.financials

    candidates: List[float] = []

    if val and val.forward_growth_rate is not None and val.forward_growth_rate != 0.0:
        candidates.append(val.forward_growth_rate)
    if val and val.fcf_cagr is not None:
        candidates.append(val.fcf_cagr)
    if fin and fin.net_income_growth is not None:
        candidates.append(fin.net_income_growth)
    if fin and fin.revenue_growth_rate is not None:
        candidates.append(fin.revenue_growth_rate)

    if not candidates:
        logger.debug(
            "No stock-specific growth signal found for %s; using fallback %.0f%%.",
            stock_metrics.profile.ticker,
            _FALLBACK_BASE_GROWTH * 100,
        )
        return _FALLBACK_BASE_GROWTH

    base = sum(candidates) / len(candidates)
    clamped = max(_GROWTH_FLOOR, min(_GROWTH_CEILING, base))

    if clamped != base:
        logger.debug(
            "Base growth for %s clamped from %.2f%% to %.2f%%.",
            stock_metrics.profile.ticker,
            base * 100,
            clamped * 100,
        )
    return clamped


def generate_growth_scenarios(
    stock_metrics: StockMetrics,
    projection_years: int,
    margin_of_safety: float = 0.25,
    random_seed: Optional[int] = None,
) -> Dict[str, List[float]]:
    """
    Generate Bear / Base / Bull growth-rate scenarios.

    Fix 4: previously called ``random.seed(random_seed)`` which mutates the
    *global* PRNG state.  In any environment with concurrency (threaded tests,
    async servers) this makes outputs non-deterministic even when a seed is
    supplied.  We now use ``random.Random(random_seed)`` — a fully isolated
    PRNG instance — so callers get reproducible results without side-effects on
    anything else that uses the standard ``random`` module.
    """
    # Local PRNG: None seed → non-deterministic (same behaviour as before when
    # no seed was passed); integer seed → fully reproducible for that call only.
    rng = random.Random(random_seed)

    sector: Sectors = stock_metrics.profile.sector
    base_growth = _derive_base_growth(stock_metrics)

    scenarios: Dict[str, List[float]] = {}

    for scenario_name in ("Bear", "Base", "Bull"):
        multiplier = SECTOR_SCENARIO_MULTIPLIERS[scenario_name].get(sector, 1.0)
        volatility = SECTOR_VOLATILITY[scenario_name].get(sector, 0.005)

        if scenario_name == "Bear":
            multiplier *= (1.0 - margin_of_safety)
        elif scenario_name == "Bull":
            multiplier *= (1.0 + margin_of_safety)

        growth_list: List[float] = []
        for _ in range(projection_years):
            noise = rng.uniform(-volatility, volatility)
            raw = base_growth * multiplier + noise
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