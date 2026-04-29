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

# Minimum absolute value a growth signal's denominator must have to be
# considered reliable.  Signals derived from near-zero denominators
# (e.g. FCF transitioning from -$1M to +$2M) would produce astronomically
# large and meaningless CAGRs.
_MIN_ABS_FCF_FOR_CAGR = 1_000_000   # $1 M


def _default_seed(ticker: str) -> int:
    key    = f"{ticker.upper()}:{date.today().isoformat()}"
    digest = hashlib.sha256(key.encode()).hexdigest()
    return int(digest[:16], 16)


def _derive_base_growth(stock_metrics: StockMetrics) -> float:
    """
    DESIGN-1 fix: priority-ordered growth signal selection instead of blind averaging.

    Priority:
    1. forward_growth_rate  (prospective NI/EPS CAGR — most relevant for DCF/PE/ROE)
    2. fcf_cagr             (if finite, positive, and derived from adequate FCF scale)
    3. net_income_growth TTM (point-in-time — volatile, last resort for profitable cos)
    4. revenue_growth_rate  (weakest earnings signal, final fallback)

    BUG-G fix: net_income_growth is disqualified as a valid signal when
    net_income_ttm is negative.  A ratio of two negative numbers trending
    "less negative" (e.g. −$434M → −$279M = +55% apparent growth) is not
    economically meaningful and would seed grossly optimistic projections for
    loss-making companies.

    BUG-D fix: when any signal is clamped by _GROWTH_CEILING or _GROWTH_FLOOR,
    emit a logger.warning so the clip is auditable.  The existing silent clamp
    made it impossible to tell from logs why the Bull scenario growth appeared
    conservative for high-growth names.
    """
    val    = stock_metrics.valuation
    fin    = stock_metrics.financials
    cf     = stock_metrics.cash_flow
    ticker = stock_metrics.profile.ticker

    def _clamp_and_warn(raw: float, source: str) -> float:
        """Clamp raw to [_GROWTH_FLOOR, _GROWTH_CEILING] and warn if clamped."""
        clamped = max(_GROWTH_FLOOR, min(_GROWTH_CEILING, raw))
        if clamped != raw:
            logger.warning(
                "[%s] Growth signal '%s' = %.1f%% was clamped to %.1f%% "
                "(floor=%.0f%%, ceiling=%.0f%%).  "
                "Check whether the signal is reliable for this company.",
                ticker,
                source,
                raw * 100,
                clamped * 100,
                _GROWTH_FLOOR * 100,
                _GROWTH_CEILING * 100,
            )
        return clamped

    # ── Priority 1: forward_growth_rate ──────────────────────────────────────
    if val and val.forward_growth_rate != 0.0 and math.isfinite(val.forward_growth_rate):
        clamped = _clamp_and_warn(val.forward_growth_rate, "forward_growth_rate")
        logger.debug("[%s] Base growth from forward_growth_rate: %.2f%%", ticker, clamped * 100)
        return clamped

    # ── Priority 2: FCF CAGR ─────────────────────────────────────────────────
    # Only when positive (negative CAGR from sign-crossing is noise) AND the
    # FCF values it was derived from are large enough to be meaningful.
    if val and val.fcf_cagr != 0.0 and math.isfinite(val.fcf_cagr) and val.fcf_cagr > 0:
        # Additional scale guard: discard if the FCF history that produced the
        # CAGR contains values too small to be reliable.
        fcf_series = cf.history.fcf_annual if (cf.history is not None) else None
        fcf_scale_ok = True
        if fcf_series:
            if any(abs(v) < _MIN_ABS_FCF_FOR_CAGR for v in fcf_series if v is not None):
                fcf_scale_ok = False
                logger.debug(
                    "[%s] fcf_cagr skipped: FCF series contains near-zero values "
                    "(< $1M) that make the CAGR unreliable.",
                    ticker,
                )
        if fcf_scale_ok:
            clamped = _clamp_and_warn(val.fcf_cagr, "fcf_cagr")
            logger.debug("[%s] Base growth from fcf_cagr: %.2f%%", ticker, clamped * 100)
            return clamped

    # ── Priority 3: TTM net income growth ────────────────────────────────────
    # BUG-G fix: disqualify this signal entirely when net_income_ttm is negative.
    # A ratio of two negative numbers can appear as large positive growth but
    # carries no forward-looking information for a loss-making company.
    if fin and fin.net_income_growth != 0.0 and math.isfinite(fin.net_income_growth):
        if fin.net_income_ttm < 0:
            logger.debug(
                "[%s] net_income_growth (%.1f%%) disqualified: net_income_ttm is "
                "negative (%.0f).  Ratio of two negative numbers is not a valid "
                "forward growth signal.",
                ticker,
                fin.net_income_growth * 100,
                fin.net_income_ttm,
            )
            # Fall through to next signal
        else:
            clamped = _clamp_and_warn(fin.net_income_growth, "net_income_growth")
            logger.debug("[%s] Base growth from net_income_growth: %.2f%%", ticker, clamped * 100)
            return clamped

    # ── Priority 4: TTM revenue growth ───────────────────────────────────────
    if fin and fin.revenue_growth_rate != 0.0 and math.isfinite(fin.revenue_growth_rate):
        clamped = _clamp_and_warn(fin.revenue_growth_rate, "revenue_growth_rate")
        logger.debug("[%s] Base growth from revenue_growth_rate: %.2f%%", ticker, clamped * 100)
        return clamped

    logger.warning(
        "[%s] No valid growth signal found; using fallback %.0f%%.  "
        "All signals were either zero, non-finite, or disqualified (negative income).",
        ticker,
        _FALLBACK_BASE_GROWTH * 100,
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
        floor_clipped   = False
        for _ in range(projection_years):
            noise   = rng.uniform(-volatility, volatility)
            raw     = base_growth * multiplier + noise
            clipped = max(_GROWTH_FLOOR, min(_GROWTH_CEILING, raw))
            if clipped != raw:
                if raw > _GROWTH_CEILING:
                    ceiling_clipped = True
                else:
                    floor_clipped = True
            growth_list.append(clipped)

        # BUG-D fix: emit diagnostics when ceiling/floor binds in any scenario.
        # Previously only Bull ceiling was logged (and only at DEBUG level).
        # Now both ceiling and floor clips are warned for all scenarios so the
        # clip is visible in standard INFO-level log output.
        if ceiling_clipped:
            logger.warning(
                "[%s] %s scenario: growth ceiling (%.0f%%) was binding for ≥1 year.  "
                "Projected growth rates are capped — scenario may be conservative.",
                stock_metrics.profile.ticker,
                scenario_name,
                _GROWTH_CEILING * 100,
            )
        if floor_clipped:
            logger.warning(
                "[%s] %s scenario: growth floor (%.0f%%) was binding for ≥1 year.  "
                "Projected contraction is capped — scenario may understate downside.",
                stock_metrics.profile.ticker,
                scenario_name,
                _GROWTH_FLOOR * 100,
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