import math
from typing import Dict, List, Optional

from calculations.dfc_formulas import cost_of_equity_capm
from calculations.metrics_formulas import cagr_from_series
from config.config_loader import load_valuation_config
from domain.metrics.stock import StockMetrics
from domain.valuation.models.ddm import (
    DDMParameters,
    DDMValuationReport,
    DDMValuationResult,
)

from ..utils import evaluate_price
from .defaults import get_params

_FALLBACK_DIV_GROWTH = 0.03


def _implied_required_return(dps: float, growth_rates: List[float], terminal_g: float,
                              price: float, projection_years: int) -> float:
    """
    Binary search for r such that PV(dividends) + PV(terminal) = price.
    Returns 0.0 if no solution found in [0.01, 0.50].
    """
    if price <= 0 or dps <= 0:
        return 0.0
    lo, hi = 0.001, 0.50
    for _ in range(100):
        mid  = (lo + hi) / 2
        div  = dps
        pv   = 0.0
        for k, g in enumerate(growth_rates, 1):
            div *= (1 + g)
            pv  += div / (1 + mid) ** k
        # Terminal value at year N
        d_next = div * (1 + terminal_g)
        if mid <= terminal_g:
            hi = mid
            continue
        tv  = d_next / (mid - terminal_g)
        pv += tv / (1 + mid) ** projection_years
        if pv > price:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2, 6)


def ddm_valuation(
    stock_metrics: StockMetrics,
    growth_rates: List[float],
    params: DDMParameters,
    dps_ttm: float,
    scenario: str,
) -> DDMValuationResult:
    """
    Single DDM scenario.

    Formula (Gordon Growth with projection window):
        For years 1..N: compound D0 by growth_rates
        Terminal value at year N: D_{N+1} / (r − g)
        IV = PV(D_1..D_N) + PV(terminal value)
    """
    beta = stock_metrics.market_data.beta or 1.0
    required_return = cost_of_equity_capm(
        params.risk_free_rate, beta, params.market_risk_premium
    )

    if required_return <= params.terminal_growth_rate:
        raise ValueError(
            f"required_return ({required_return:.3f}) must exceed terminal_growth_rate "
            f"({params.terminal_growth_rate:.3f}) for Gordon Growth DDM."
        )

    dividend  = dps_ttm
    div_prog: List[float] = []
    pv_sum    = 0.0

    for k, g in enumerate(growth_rates, 1):
        dividend *= (1 + g)
        div_prog.append(dividend)
        pv_sum  += dividend / (1 + required_return) ** k

    # Terminal value: next dividend after projection window
    terminal_div = dividend * (1 + params.terminal_growth_rate)
    tv           = terminal_div / (required_return - params.terminal_growth_rate)
    pv_tv        = tv / (1 + required_return) ** params.projection_years
    iv           = pv_sum + pv_tv

    status = evaluate_price(
        current_price=stock_metrics.market_data.current_price,
        intrinsic_value=iv,
    )

    implied_r = _implied_required_return(
        dps_ttm, growth_rates, params.terminal_growth_rate,
        stock_metrics.market_data.current_price, params.projection_years,
    )
    dividend_yield_implied = (
        div_prog[0] / iv if iv > 0 and div_prog else 0.0
    )

    return DDMValuationResult(
        scenario=scenario,
        growth_rates=growth_rates,
        dividend_progression=div_prog,
        terminal_dividend=terminal_div,
        required_return=required_return,
        terminal_value=tv,
        pv_dividends=pv_sum,
        pv_terminal_value=pv_tv,
        intrinsic_value_per_share=iv,
        implied_required_return=implied_r,
        dividend_yield_implied=dividend_yield_implied,
        valuation_status=status,
    )


def _dividend_growth_rate(stock_metrics: StockMetrics) -> float:
    """Derive historical dividend growth CAGR from annual dividend history."""
    cf = stock_metrics.cash_flow
    dividends_paid_annual = (
        getattr(cf.history, "dividends_paid_annual", None)
        if cf.history is not None else None
    )
    if dividends_paid_annual:
        series = [abs(v) for v in dividends_paid_annual if v]
        if len(series) >= 2:
            cagr = cagr_from_series(series)
            if cagr is not None and math.isfinite(cagr) and cagr > 0:
                return min(cagr, 0.15)  # cap at 15% to avoid outliers
    return _FALLBACK_DIV_GROWTH


def _build_dividend_growth_scenarios(
    stock_metrics: StockMetrics,
    params: DDMParameters,
    dividend_growth: float,
) -> Dict[str, List[float]]:
    """Build fixed DDM dividend-growth paths from dividend-specific history."""
    scen_cfg = load_valuation_config("scenarios")
    sector = stock_metrics.profile.sector

    scenarios: Dict[str, List[float]] = {}
    for scenario_name in ("Bear", "Base", "Bull"):
        multiplier = scen_cfg.get_nested_float(
            "scenario_multipliers", scenario_name, sector, default=1.0
        )
        if scenario_name == "Bear":
            multiplier *= (1.0 - params.margin_of_safety)
        elif scenario_name == "Bull":
            multiplier *= (1.0 + params.margin_of_safety)

        scenario_growth = [dividend_growth * multiplier] * params.projection_years
        scenarios[scenario_name] = [max(-0.10, min(0.20, g)) for g in scenario_growth]

    return scenarios


def execute_ddm_scenarios(
    stock_metrics: StockMetrics,
    params: Optional[DDMParameters] = None,
) -> DDMValuationReport:
    if params is None:
        params = get_params(stock_metrics)

    shares = stock_metrics.market_data.shares_outstanding
    if not shares or shares <= 0:
        raise ValueError("shares_outstanding must be positive for DDM per-share calc.")

    div_total = abs(stock_metrics.cash_flow.dividends_paid_ttm)
    dps_ttm   = div_total / shares

    div_growth = _dividend_growth_rate(stock_metrics)

    growth_scenarios = _build_dividend_growth_scenarios(stock_metrics, params, div_growth)

    ddm_scenarios: Dict[str, DDMValuationResult] = {}
    for scenario_name, scenario_growth in growth_scenarios.items():
        ddm_scenarios[scenario_name] = ddm_valuation(
            stock_metrics=stock_metrics,
            growth_rates=scenario_growth,
            params=params,
            dps_ttm=dps_ttm,
            scenario=scenario_name,
        )

    return DDMValuationReport(
        scenarios=ddm_scenarios,
        params=params,
        dps_ttm=dps_ttm,
        dividend_growth_rate=div_growth,
    )
