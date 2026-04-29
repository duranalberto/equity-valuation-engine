"""
application/valuations/utils.py

Phase 3 additions
-----------------
DESIGN-A: WeightedGrowthSignal dataclass + confidence-weighted blend of all
          valid growth signals.  Weighted blending is opt-in via valuation
          params; the default remains the Phase 1/2 priority waterfall.

DESIGN-B: Sector-aware linear mean-reversion in generate_growth_scenarios().
          Mean reversion is opt-in via valuation params.  When enabled, each
          year's growth rate tapers linearly toward the sector long-run growth
          rate loaded from scenarios.yaml. Bear scenarios revert faster
          (speed=1.3×); Bull scenarios revert slower (0.7×).
"""
import hashlib
import logging
import math
import random
from dataclasses import dataclass, replace
from datetime import date
from typing import Dict, List, Optional, Tuple

from config.config_loader import load_valuation_config
from domain.metrics.stock import StockMetrics
from domain.valuation.base import (
    GrowthAssumption,
    GrowthModel,
    GrowthScenarioSet,
    GrowthSignalContribution,
)

logger = logging.getLogger(__name__)

_scenarios_cfg = load_valuation_config("scenarios")

_GROWTH_FLOOR         = -0.20
_GROWTH_CEILING       =  0.50
_FALLBACK_BASE_GROWTH =  0.04

# Minimum absolute FCF value for a CAGR signal to be considered reliable.
_MIN_ABS_FCF_FOR_CAGR = 1_000_000   # $1 M

# ─── DESIGN-A: confidence weights ────────────────────────────────────────────
# Sum does NOT need to equal 1.0 — weights are normalised at blend time.
# Order: forward_ni_cagr, fcf_cagr, eps_cagr (via forward_growth alt),
#        ttm_ni_growth, revenue_growth.
_SIGNAL_WEIGHTS: Dict[str, float] = {
    "forward_ni_cagr":  0.40,
    "fcf_cagr":         0.25,
    "eps_cagr":         0.20,   # used only when forward_ni_cagr != forward_growth_rate
    "ttm_ni_growth":    0.10,
    "revenue_growth":   0.05,
}

# Minimum number of valid signals required to use the blend.
# Below this threshold the priority waterfall is used instead.
_MIN_SIGNALS_FOR_BLEND = 3


# ─── DESIGN-A: dataclass ─────────────────────────────────────────────────────

@dataclass(frozen=True)
class WeightedGrowthSignal:
    """
    A single growth signal with its source label, raw value, and confidence
    weight before normalisation.

    ``clamped_value`` is the value after applying [_GROWTH_FLOOR, _GROWTH_CEILING].
    ``raw_value`` is the pre-clamp value, preserved for diagnostics.
    """
    source:        str
    raw_value:     float
    clamped_value: float
    weight:        float


def _default_seed(ticker: str) -> int:
    key    = f"{ticker.upper()}:{date.today().isoformat()}"
    digest = hashlib.sha256(key.encode()).hexdigest()
    return int(digest[:16], 16)


# ─── DESIGN-A: signal collection ─────────────────────────────────────────────

def _collect_growth_signals(
    stock_metrics: StockMetrics,
) -> Tuple[List[WeightedGrowthSignal], List[str]]:
    """
    Collect ALL valid growth signals in parallel and return them as a list of
    ``WeightedGrowthSignal`` objects.

    A signal is *valid* when:
      - its numeric value is finite and non-zero, AND
      - it passes any signal-specific quality guard (see inline comments).

    Signals are NOT priority-ordered here — all valid ones are returned so the
    caller can blend or fall back as needed.
    """
    val    = stock_metrics.valuation
    fin    = stock_metrics.financials
    cf     = stock_metrics.cash_flow
    ticker = stock_metrics.profile.ticker
    signals: List[WeightedGrowthSignal] = []
    diagnostics: List[str] = []

    def _clamp(raw: float, source: str) -> float:
        clamped = max(_GROWTH_FLOOR, min(_GROWTH_CEILING, raw))
        if clamped != raw:
            diagnostics.append(
                f"Growth signal '{source}' was clamped from {raw:.1%} to "
                f"{clamped:.1%}."
            )
            logger.warning(
                "[%s] Growth signal '%s' = %.1f%% was clamped to %.1f%% "
                "(floor=%.0f%%, ceiling=%.0f%%).",
                ticker, source, raw * 100, clamped * 100,
                _GROWTH_FLOOR * 100, _GROWTH_CEILING * 100,
            )
        return clamped

    # ── Signal 1: forward_ni_cagr (NI CAGR from annual history) ──────────────
    if val and val.forward_growth_rate != 0.0 and math.isfinite(val.forward_growth_rate):
        raw     = val.forward_growth_rate
        clamped = _clamp(raw, "forward_ni_cagr")
        signals.append(WeightedGrowthSignal(
            source="forward_ni_cagr",
            raw_value=raw,
            clamped_value=clamped,
            weight=_SIGNAL_WEIGHTS["forward_ni_cagr"],
        ))

    # ── Signal 2: FCF CAGR ────────────────────────────────────────────────────
    # Only positive, finite, and derived from an adequately-scaled FCF series.
    if val and val.fcf_cagr != 0.0 and math.isfinite(val.fcf_cagr) and val.fcf_cagr > 0:
        fcf_series  = cf.history.fcf_annual if (cf.history is not None) else None
        fcf_scale_ok = True
        if fcf_series:
            if any(abs(v) < _MIN_ABS_FCF_FOR_CAGR for v in fcf_series if v is not None):
                fcf_scale_ok = False
                diagnostics.append(
                    "fcf_cagr signal skipped in weighted blend because the FCF "
                    "series contains values below $1M."
                )
                logger.debug(
                    "[%s] fcf_cagr signal skipped in blend: FCF series contains "
                    "near-zero values (< $1M).", ticker,
                )
        if fcf_scale_ok:
            raw     = val.fcf_cagr
            clamped = _clamp(raw, "fcf_cagr")
            signals.append(WeightedGrowthSignal(
                source="fcf_cagr",
                raw_value=raw,
                clamped_value=clamped,
                weight=_SIGNAL_WEIGHTS["fcf_cagr"],
            ))

    # ── Signal 3: EPS CAGR ────────────────────────────────────────────────────
    # forward_growth_rate is computed from NI history OR EPS history (whichever
    # fires first in Valuation.build).  When it came from EPS history it already
    # sits in forward_ni_cagr above; we only add a separate eps_cagr entry when
    # it is *distinct* — i.e. when the underlying EPS series differs from NI.
    # In practice Valuation.build() merges them, so this slot acts as a
    # tiebreaker when net_income_annual is absent but eps_history is present.
    # We proxy this by checking whether eps_ttm is available and positive.
    if (fin and fin.net_income_ttm > 0
            and stock_metrics.historical_data is not None
            and stock_metrics.historical_data.eps_history is not None
            and len(stock_metrics.historical_data.eps_history) >= 2):
        from calculations.metrics_formulas import cagr_from_series
        eps_cagr = cagr_from_series(stock_metrics.historical_data.eps_history)
        if eps_cagr is not None and eps_cagr != 0.0 and math.isfinite(eps_cagr):
            # Only add if it is meaningfully different from forward_ni_cagr
            existing = {s.source for s in signals}
            if "forward_ni_cagr" not in existing or abs(eps_cagr - val.forward_growth_rate) > 0.005:
                raw     = eps_cagr
                clamped = _clamp(raw, "eps_cagr")
                signals.append(WeightedGrowthSignal(
                    source="eps_cagr",
                    raw_value=raw,
                    clamped_value=clamped,
                    weight=_SIGNAL_WEIGHTS["eps_cagr"],
                ))

    # ── Signal 4: TTM net income growth ──────────────────────────────────────
    # BUG-G fix preserved: disqualify when net_income_ttm is negative.
    if fin and fin.net_income_growth != 0.0 and math.isfinite(fin.net_income_growth):
        if fin.net_income_ttm < 0:
            logger.debug(
                "[%s] net_income_growth (%.1f%%) excluded from blend: "
                "net_income_ttm is negative (%.0f).",
                ticker, fin.net_income_growth * 100, fin.net_income_ttm,
            )
        else:
            raw     = fin.net_income_growth
            clamped = _clamp(raw, "ttm_ni_growth")
            signals.append(WeightedGrowthSignal(
                source="ttm_ni_growth",
                raw_value=raw,
                clamped_value=clamped,
                weight=_SIGNAL_WEIGHTS["ttm_ni_growth"],
            ))

    # ── Signal 5: TTM revenue growth ─────────────────────────────────────────
    if fin and fin.revenue_growth_rate != 0.0 and math.isfinite(fin.revenue_growth_rate):
        raw     = fin.revenue_growth_rate
        clamped = _clamp(raw, "revenue_growth")
        signals.append(WeightedGrowthSignal(
            source="revenue_growth",
            raw_value=raw,
            clamped_value=clamped,
            weight=_SIGNAL_WEIGHTS["revenue_growth"],
        ))

    return signals, diagnostics


def _blend_signals(
    signals: List[WeightedGrowthSignal],
    ticker: str,
) -> Tuple[float, List[WeightedGrowthSignal]]:
    """
    Compute the confidence-weighted blend of valid signals.

    Returns (blended_rate, signals_used).

    Weights are normalised to sum to 1.0 before blending so that missing
    signals do not dilute the result — only the signals that are present
    contribute.
    """
    total_weight = sum(s.weight for s in signals)
    if total_weight <= 0:
        return _FALLBACK_BASE_GROWTH, []

    blended = sum(s.clamped_value * s.weight for s in signals) / total_weight

    logger.debug(
        "[%s] Blended growth rate = %.2f%% from %d signals: %s",
        ticker,
        blended * 100,
        len(signals),
        ", ".join(f"{s.source}={s.clamped_value:.1%}(w={s.weight:.2f})" for s in signals),
    )
    return blended, signals


# ─── DESIGN-A: growth assumption derivation ──────────────────────────────────


def _signal_to_contribution(signal: WeightedGrowthSignal) -> GrowthSignalContribution:
    return GrowthSignalContribution(
        source=signal.source,
        raw_value=signal.raw_value,
        clamped_value=signal.clamped_value,
        weight=signal.weight,
    )


def _derive_growth_assumption(
    stock_metrics: StockMetrics,
    growth_model: GrowthModel = "waterfall",
) -> GrowthAssumption:
    if growth_model not in ("waterfall", "weighted_blend"):
        raise ValueError(
            f"Unsupported growth_model {growth_model!r}. "
            "Expected 'waterfall' or 'weighted_blend'."
        )

    if growth_model == "waterfall":
        return _priority_waterfall_assumption(stock_metrics, requested_mode=growth_model)

    ticker = stock_metrics.profile.ticker
    signals, diagnostics = _collect_growth_signals(stock_metrics)

    if len(signals) >= _MIN_SIGNALS_FOR_BLEND:
        blended, used = _blend_signals(signals, ticker)
        logger.info(
            "[%s] Using BLENDED growth rate = %.2f%% (%d signals).",
            ticker, blended * 100, len(used),
        )
        return GrowthAssumption(
            requested_mode=growth_model,
            selected_mode="weighted_blend",
            selected_rate=blended,
            selected_source="weighted_blend",
            signals=[_signal_to_contribution(signal) for signal in used],
            diagnostics=diagnostics,
        )

    diagnostic = (
        f"weighted_blend requested but only {len(signals)} valid growth "
        f"signal(s) were available; used waterfall instead"
    )
    logger.debug(
        "[%s] Only %d valid signal(s) — falling back to priority waterfall.",
        ticker, len(signals),
    )
    assumption = _priority_waterfall_assumption(stock_metrics, requested_mode=growth_model)
    return GrowthAssumption(
        requested_mode=assumption.requested_mode,
        selected_mode=assumption.selected_mode,
        selected_rate=assumption.selected_rate,
        selected_source=assumption.selected_source,
        signals=assumption.signals,
        diagnostics=[*diagnostics, *assumption.diagnostics, diagnostic],
    )


def _derive_base_growth(
    stock_metrics: StockMetrics,
    growth_model: GrowthModel = "waterfall",
) -> float:
    """Return the base growth rate used to seed all scenario projections."""
    return _derive_growth_assumption(stock_metrics, growth_model).selected_rate


def _priority_waterfall(stock_metrics: StockMetrics) -> float:
    return _priority_waterfall_assumption(stock_metrics).selected_rate


def _priority_waterfall_assumption(
    stock_metrics: StockMetrics,
    requested_mode: GrowthModel = "waterfall",
) -> GrowthAssumption:
    """
    Original Phase 1/2 priority-ordered growth selection.

    Preserved as the default behavior for backwards compatibility.
    """
    val    = stock_metrics.valuation
    fin    = stock_metrics.financials
    cf     = stock_metrics.cash_flow
    ticker = stock_metrics.profile.ticker
    diagnostics: List[str] = []

    def _clamp_and_warn(raw: float, source: str) -> float:
        clamped = max(_GROWTH_FLOOR, min(_GROWTH_CEILING, raw))
        if clamped != raw:
            diagnostics.append(
                f"Growth signal '{source}' was clamped from {raw:.1%} to "
                f"{clamped:.1%}."
            )
            logger.warning(
                "[%s] Growth signal '%s' = %.1f%% was clamped to %.1f%% "
                "(floor=%.0f%%, ceiling=%.0f%%).  "
                "Check whether the signal is reliable for this company.",
                ticker, source, raw * 100, clamped * 100,
                _GROWTH_FLOOR * 100, _GROWTH_CEILING * 100,
            )
        return clamped

    def _assumption(source: str, raw: float, clamped: float) -> GrowthAssumption:
        return GrowthAssumption(
            requested_mode=requested_mode,
            selected_mode="waterfall",
            selected_rate=clamped,
            selected_source=source,
            signals=[
                GrowthSignalContribution(
                    source=source,
                    raw_value=raw,
                    clamped_value=clamped,
                    weight=1.0,
                )
            ],
            diagnostics=list(diagnostics),
        )

    # Priority 1: forward_growth_rate
    if val and val.forward_growth_rate != 0.0 and math.isfinite(val.forward_growth_rate):
        clamped = _clamp_and_warn(val.forward_growth_rate, "forward_growth_rate")
        logger.debug("[%s] Base growth from forward_growth_rate: %.2f%%", ticker, clamped * 100)
        return _assumption("forward_growth_rate", val.forward_growth_rate, clamped)

    # Priority 2: FCF CAGR
    if val and val.fcf_cagr != 0.0 and math.isfinite(val.fcf_cagr) and val.fcf_cagr > 0:
        fcf_series   = cf.history.fcf_annual if (cf.history is not None) else None
        fcf_scale_ok = True
        if fcf_series:
            if any(abs(v) < _MIN_ABS_FCF_FOR_CAGR for v in fcf_series if v is not None):
                fcf_scale_ok = False
                diagnostics.append(
                    "fcf_cagr skipped because the FCF series contains values "
                    "below $1M."
                )
                logger.debug(
                    "[%s] fcf_cagr skipped: FCF series contains near-zero values.", ticker,
                )
        if fcf_scale_ok:
            clamped = _clamp_and_warn(val.fcf_cagr, "fcf_cagr")
            logger.debug("[%s] Base growth from fcf_cagr: %.2f%%", ticker, clamped * 100)
            return _assumption("fcf_cagr", val.fcf_cagr, clamped)

    # Priority 3: TTM net income growth (BUG-G guard preserved)
    if fin and fin.net_income_growth != 0.0 and math.isfinite(fin.net_income_growth):
        if fin.net_income_ttm < 0:
            logger.debug(
                "[%s] net_income_growth (%.1f%%) disqualified: net_income_ttm is negative.",
                ticker, fin.net_income_growth * 100,
            )
        else:
            clamped = _clamp_and_warn(fin.net_income_growth, "net_income_growth")
            logger.debug("[%s] Base growth from net_income_growth: %.2f%%", ticker, clamped * 100)
            return _assumption("net_income_growth", fin.net_income_growth, clamped)

    # Priority 4: TTM revenue growth
    if fin and fin.revenue_growth_rate != 0.0 and math.isfinite(fin.revenue_growth_rate):
        clamped = _clamp_and_warn(fin.revenue_growth_rate, "revenue_growth_rate")
        logger.debug("[%s] Base growth from revenue_growth_rate: %.2f%%", ticker, clamped * 100)
        return _assumption("revenue_growth_rate", fin.revenue_growth_rate, clamped)

    diagnostic = (
        f"No valid growth signal found; using fallback "
        f"{_FALLBACK_BASE_GROWTH:.0%}."
    )
    logger.warning(
        "[%s] No valid growth signal found; using fallback %.0f%%.  "
        "All signals were either zero, non-finite, or disqualified.",
        ticker, _FALLBACK_BASE_GROWTH * 100,
    )
    return GrowthAssumption(
        requested_mode=requested_mode,
        selected_mode="waterfall",
        selected_rate=_FALLBACK_BASE_GROWTH,
        selected_source="fallback",
        signals=[
            GrowthSignalContribution(
                source="fallback",
                raw_value=_FALLBACK_BASE_GROWTH,
                clamped_value=_FALLBACK_BASE_GROWTH,
                weight=1.0,
            )
        ],
        diagnostics=[diagnostic],
    )


# ─── DESIGN-B: mean-reversion helper ─────────────────────────────────────────

def _apply_mean_reversion(
    year_index: int,          # 0-based (0 = year 1)
    projection_years: int,
    base_growth: float,
    long_run_growth: float,
    reversion_speed: float,
) -> float:
    """
    Compute the mean-reverted growth rate for a given year.

    Formula:
        reverted = base + (long_run - base) * (k / N) * speed

    where k = year_index + 1  (1-based year number)
          N = projection_years

    At year 0  → reverted ≈ base_growth
    At year N  → reverted ≈ long_run_growth (when speed=1.0)

    Bear (speed=1.3): converges faster — pessimistic
    Base (speed=1.0): standard linear
    Bull (speed=0.7): converges slower — optimistic (growth stays higher longer)
    """
    k = year_index + 1
    t = min(k / projection_years, 1.0) * reversion_speed
    t = min(t, 1.0)   # clamp so speed > 1 doesn't overshoot
    return base_growth + (long_run_growth - base_growth) * t


# ─── Main public function ─────────────────────────────────────────────────────

def generate_growth_scenarios(
    stock_metrics: StockMetrics,
    projection_years: int,
    margin_of_safety: float = 0.25,
    random_seed: Optional[int] = None,
    stochastic: bool = False,
    reversion_enabled: bool = False,
    growth_model: GrowthModel = "waterfall",
) -> Dict[str, List[float]]:
    """Compatibility wrapper returning only scenario growth-rate lists."""
    return generate_growth_scenarios_with_assumption(
        stock_metrics=stock_metrics,
        projection_years=projection_years,
        margin_of_safety=margin_of_safety,
        random_seed=random_seed,
        stochastic=stochastic,
        reversion_enabled=reversion_enabled,
        growth_model=growth_model,
    ).scenarios


def generate_growth_scenarios_with_assumption(
    stock_metrics: StockMetrics,
    projection_years: int,
    margin_of_safety: float = 0.25,
    random_seed: Optional[int] = None,
    stochastic: bool = False,
    reversion_enabled: bool = False,
    growth_model: GrowthModel = "waterfall",
) -> GrowthScenarioSet:
    """
    Generate Bear / Base / Bull growth rate lists for the projection window.

    DESIGN-A: base growth uses the Phase 1/2 waterfall by default.  The
    confidence-weighted blend is used only when requested and enough valid
    signals exist.

    DESIGN-B: when reversion_enabled=True AND the stock's sector has a
    long-run growth rate configured in scenarios.yaml, each year's rate is
    linearly tapered toward the sector long-run mean.  Bear reverts faster
    (1.3×), Bull reverts slower (0.7×).
    """
    seed = random_seed if random_seed is not None else None
    rng         = random.Random(seed)
    sector      = stock_metrics.profile.sector
    ticker      = stock_metrics.profile.ticker
    assumption  = _derive_growth_assumption(stock_metrics, growth_model)
    base_growth = assumption.selected_rate

    # ── DESIGN-B: load long-run growth and reversion speeds ──────────────────
    long_run_growth: Optional[float] = None
    diagnostics = list(assumption.diagnostics)
    if reversion_enabled:
        raw_lr = _scenarios_cfg.get_float("sector_long_run_growth", sector, default=0.0)
        if raw_lr != 0.0:
            long_run_growth = raw_lr
            logger.debug(
                "[%s] Mean-reversion enabled: base=%.2f%%, long_run=%.2f%% (%s sector).",
                ticker, base_growth * 100, long_run_growth * 100,
                sector.value if sector else "unknown",
            )
        else:
            logger.debug(
                "[%s] Mean-reversion enabled but no sector_long_run_growth configured — "
                "reversion skipped.", ticker,
            )
            diagnostics.append(
                "reversion_enabled requested but no sector long-run growth "
                "was configured; generated flat non-reverted scenarios"
            )

    # Load per-scenario reversion speed multipliers from config.
    # These are global (not sector-specific) so we use a raw YAML section read.
    reversion_speeds: Dict[str, float] = {}
    if long_run_growth is not None:
        speed_section = _scenarios_cfg.raw_section("reversion_speed")
        reversion_speeds = {
            "Bear": float(speed_section.get("Bear", 1.3)),
            "Base": float(speed_section.get("Base", 1.0)),
            "Bull": float(speed_section.get("Bull", 0.7)),
        }

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

        reversion_speed = reversion_speeds.get(scenario_name, 1.0)

        growth_list: List[float] = []
        ceiling_clipped = False
        floor_clipped   = False

        for year_idx in range(projection_years):
            # Scenario-scaled base for this year before mean-reversion
            scaled_base = base_growth * multiplier

            # DESIGN-B: apply linear mean-reversion if configured
            if long_run_growth is not None:
                # Mean-revert the *scenario-scaled* base (not raw base_growth)
                # so Bear/Bull multipliers still influence the reversion path.
                reverted = _apply_mean_reversion(
                    year_index=year_idx,
                    projection_years=projection_years,
                    base_growth=scaled_base,
                    long_run_growth=long_run_growth,
                    reversion_speed=reversion_speed,
                )
            else:
                reverted = scaled_base

            noise   = rng.uniform(-volatility, volatility) if stochastic else 0.0
            raw     = reverted + noise
            clipped = max(_GROWTH_FLOOR, min(_GROWTH_CEILING, raw))

            if clipped != raw:
                if raw > _GROWTH_CEILING:
                    ceiling_clipped = True
                else:
                    floor_clipped = True

            growth_list.append(clipped)

        # BUG-D: emit diagnostics when ceiling/floor binds in any scenario.
        if ceiling_clipped:
            diagnostics.append(
                f"{scenario_name} scenario growth ceiling ({_GROWTH_CEILING:.0%}) "
                "was binding for at least one projected year."
            )
            logger.warning(
                "[%s] %s scenario: growth ceiling (%.0f%%) was binding for ≥1 year.  "
                "Projected growth rates are capped — scenario may be conservative.",
                ticker, scenario_name, _GROWTH_CEILING * 100,
            )
        if floor_clipped:
            diagnostics.append(
                f"{scenario_name} scenario growth floor ({_GROWTH_FLOOR:.0%}) "
                "was binding for at least one projected year."
            )
            logger.warning(
                "[%s] %s scenario: growth floor (%.0f%%) was binding for ≥1 year.  "
                "Projected contraction is capped — scenario may understate downside.",
                ticker, scenario_name, _GROWTH_FLOOR * 100,
            )

        scenarios[scenario_name] = growth_list

    # ── DESIGN-B: log mean-reversion effect summary ───────────────────────────
    if long_run_growth is not None:
        for sn, rates in scenarios.items():
            logger.debug(
                "[%s] %s scenario: year-1 growth=%.2f%%, year-%d growth=%.2f%% "
                "(long_run=%.2f%%).",
                ticker, sn, rates[0] * 100, projection_years,
                rates[-1] * 100, long_run_growth * 100,
            )

    assumption = replace(
        assumption,
        diagnostics=diagnostics,
        reversion_enabled=long_run_growth is not None,
        long_run_growth=long_run_growth,
    )
    return GrowthScenarioSet(scenarios=scenarios, assumption=assumption)


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
