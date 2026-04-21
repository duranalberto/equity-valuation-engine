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

_GROWTH_FLOOR         = -0.20
_GROWTH_CEILING       =  0.50
_FALLBACK_BASE_GROWTH =  0.04


def _default_seed(ticker: str) -> int:
    key    = f"{ticker.upper()}:{date.today().isoformat()}"
    digest = hashlib.sha256(key.encode()).hexdigest()
    return int(digest[:16], 16)


def _derive_base_growth(stock_metrics: StockMetrics) -> float:
    """
    DESIGN-1 fix: priority-ordered growth signal selection instead of blind averaging.

    Priority:
    1. forward_growth_rate (prospective CAGR — most relevant for DCF/PE/ROE)
    2. net_income CAGR from annual history (multi-year compounded — stable)
    3. fcf_cagr (if finite and positive — FCF sign changes disqualify it)
    4. net_income_growth TTM (point-in-time — most volatile, last resort)
    5. revenue_growth_rate (weakest earnings signal, final fallback)

    Signals are not averaged: the highest-priority valid signal is used.
    Each signal is validated for finiteness before use.
    A debug log records which signal was selected so the choice is auditable.
    """
    val = stock_metrics.valuation
    fin = stock_metrics.financials
    ticker = stock_metrics.profile.ticker

    # Priority 1: forward_growth_rate (from annual NI CAGR or EPS CAGR in Valuation.build)
    if val and val.forward_growth_rate != 0.0 and math.isfinite(val.forward_growth_rate):
        clamped = max(_GROWTH_FLOOR, min(_GROWTH_CEILING, val.forward_growth_rate))
        logger.debug("[%s] Base growth from forward_growth_rate: %.2f%%", ticker, clamped * 100)
        return clamped

    # Priority 2: FCF CAGR — only when positive (negative CAGR from sign-crossing is noise)
    if val and val.fcf_cagr != 0.0 and math.isfinite(val.fcf_cagr) and val.fcf_cagr > 0:
        clamped = max(_GROWTH_FLOOR, min(_GROWTH_CEILING, val.fcf_cagr))
        logger.debug("[%s] Base growth from fcf_cagr: %.2f%%", ticker, clamped * 100)
        return clamped

    # Priority 3: TTM net income growth
    if fin and fin.net_income_growth != 0.0 and math.isfinite(fin.net_income_growth):
        clamped = max(_GROWTH_FLOOR, min(_GROWTH_CEILING, fin.net_income_growth))
        logger.debug("[%s] Base growth from net_income_growth: %.2f%%", ticker, clamped * 100)
        return clamped

    # Priority 4: TTM revenue growth
    if fin and fin.revenue_growth_rate != 0.0 and math.isfinite(fin.revenue_growth_rate):
        clamped = max(_GROWTH_FLOOR, min(_GROWTH_CEILING, fin.revenue_growth_rate))
        logger.debug("[%s] Base growth from revenue_growth_rate: %.2f%%", ticker, clamped * 100)
        return clamped

    logger.debug(
        "[%s] No valid growth signal found; using fallback %.0f%%.", ticker, _FALLBACK_BASE_GROWTH * 100
    )
    return _FALLBACK_BASE_GROWTH


def generate_growth_scenarios(
    stock_metrics: StockMetrics,
    projection_years: int,
    margin_of_safety: float = 0.25,
    random_seed: Optional[int] = None,
    stochastic: bool = False,
) -> Dict[str, List[float]]:
    if random_seed is not None:
        seed = random_seed
    elif stochastic:
        seed = None
    else:
        seed = _default_seed(stock_metrics.profile.ticker)

    rng         = random.Random(seed)
    sector      = stock_metrics.profile.sector
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
        ceiling_clipped = False
        for _ in range(projection_years):
            noise = rng.uniform(-volatility, volatility)
            raw   = base_growth * multiplier + noise
            clipped = max(_GROWTH_FLOOR, min(_GROWTH_CEILING, raw))
            if clipped != raw:
                ceiling_clipped = True
            growth_list.append(clipped)

        # BUG-10 fix: log when the growth ceiling clips the Bull scenario
        if ceiling_clipped and scenario_name == "Bull":
            logger.debug(
                "[%s] Bull scenario growth ceiling (%.0f%%) was binding for one or more years. "
                "Projected growth rates are capped — Bull scenario may be conservative.",
                stock_metrics.profile.ticker, _GROWTH_CEILING * 100,
            )

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