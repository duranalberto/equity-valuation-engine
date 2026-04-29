"""
application/valuations/reverse_dcf/valuation.py

Reverse DCF: back-solve for the constant annual FCF growth rate g* such that

    DCF(g*) = current_market_price

using binary search over [search_low, search_high].

The verification step feeds g* back into the forward DCF and checks that the
resulting IV matches current_price to within 1% (surfaced in the result).
"""
from typing import Optional

from calculations.dfc_formulas import (
    compute_discounted_cash_flow,
    compute_wacc,
    cost_of_equity_capm,
    intrinsic_value_per_share,
)
from domain.metrics.stock import StockMetrics
from domain.valuation.models.reverse_dcf import (
    ReverseDCFParameters,
    ReverseDCFReport,
    ReverseDCFResult,
)

from .defaults import get_params


def _dcf_iv_for_growth(
    growth_rate: float,
    fcf_seed: float,
    projection_years: int,
    wacc: float,
    terminal_growth_rate: float,
    total_debt: float,
    cash: float,
    shares: float,
) -> float:
    """Compute DCF intrinsic value per share for a constant growth_rate."""
    fcf = fcf_seed
    projections = []
    for _ in range(projection_years):
        fcf *= (1 + growth_rate)
        projections.append(fcf)

    dcf_out, _ = compute_discounted_cash_flow(projections, wacc, terminal_growth_rate)
    equity_val  = dcf_out.enterprise_value - total_debt + cash
    return intrinsic_value_per_share(equity_val, shares)


def solve_reverse_dcf(
    stock_metrics: StockMetrics,
    params: Optional[ReverseDCFParameters] = None,
) -> ReverseDCFReport:
    """
    Binary search for implied_growth_rate such that DCF(g*) ≈ current_price.

    Returns a ReverseDCFReport containing:
    - implied_growth_rate
    - delta vs forward_growth_rate (what the market is implying vs history)
    - verification IV (re-running forward DCF with implied rate)
    - interpretation string
    """
    if params is None:
        params = get_params(stock_metrics)

    sm    = stock_metrics
    price = sm.market_data.current_price

    # Choose FCF seed: prefer normalized when capex spike detected
    if sm.valuation.capex_spike_detected and sm.valuation.normalized_fcf is not None:
        fcf_seed       = sm.valuation.normalized_fcf
        fcf_seed_source = "normalized"
    else:
        fcf_seed       = sm.cash_flow.fcf_ttm
        fcf_seed_source = "raw"

    if fcf_seed <= 0:
        raise ValueError(
            f"FCF seed ({fcf_seed:,.0f}) must be positive for Reverse DCF. "
            "Run ReverseDCFChecker.evaluate() before calling solve_reverse_dcf()."
        )

    beta = sm.market_data.beta or 1.0
    cost_of_equity = cost_of_equity_capm(
        params.risk_free_rate, beta, params.market_risk_premium
    )
    wacc_obj = compute_wacc(
        market_cap=sm.market_data.market_cap,
        total_debt=sm.balance_sheet.total_debt,
        cost_of_equity=cost_of_equity,
        cost_of_debt=sm.valuation.cost_of_debt,
        tax_rate=sm.valuation.corporate_tax_rate,
    )
    wacc = wacc_obj.wacc

    total_debt = sm.balance_sheet.total_debt
    cash       = sm.balance_sheet.cash_and_equivalents
    shares     = sm.market_data.shares_outstanding

    # Binary search
    lo, hi = params.search_low, params.search_high
    implied_g = (lo + hi) / 2.0

    for _ in range(120):
        mid = (lo + hi) / 2
        try:
            iv = _dcf_iv_for_growth(
                mid, fcf_seed, params.projection_years, wacc,
                params.terminal_growth_rate, total_debt, cash, shares,
            )
        except Exception:
            hi = mid
            continue

        if iv > price:
            hi = mid
        else:
            lo = mid

        implied_g = (lo + hi) / 2

    implied_g = round(implied_g, 6)

    # Verification
    try:
        verification_iv = _dcf_iv_for_growth(
            implied_g, fcf_seed, params.projection_years, wacc,
            params.terminal_growth_rate, total_debt, cash, shares,
        )
        verification_error_pct = abs(verification_iv - price) / price if price > 0 else None
    except Exception:
        verification_iv        = None
        verification_error_pct = None

    # Delta vs forward growth rate
    forward_g = sm.valuation.forward_growth_rate or 0.0
    delta     = implied_g - forward_g

    # Interpretation
    if delta > 0.10:
        interpretation = (
            f"Market prices in {implied_g:.1%} annual FCF growth — "
            f"{delta:.1%} above the historical forward rate ({forward_g:.1%}). "
            "Significant optimism baked in; stock may be overvalued if growth disappoints."
        )
    elif delta > 0.03:
        interpretation = (
            f"Market prices in {implied_g:.1%} growth, modestly above the historical "
            f"forward rate ({forward_g:.1%}). Valuation appears stretched but not extreme."
        )
    elif delta >= -0.03:
        interpretation = (
            f"Market prices in {implied_g:.1%} growth, broadly in line with the "
            f"historical forward rate ({forward_g:.1%}). Valuation appears reasonable."
        )
    elif delta >= -0.10:
        interpretation = (
            f"Market prices in only {implied_g:.1%} growth, {abs(delta):.1%} below "
            f"the historical forward rate ({forward_g:.1%}). "
            "Stock may be undervalued if historical growth is sustained."
        )
    else:
        interpretation = (
            f"Market prices in {implied_g:.1%} growth — {abs(delta):.1%} below the "
            f"historical forward rate ({forward_g:.1%}). "
            "Deep discount to fundamental growth expectations — potential deep value."
        )

    result = ReverseDCFResult(
        implied_growth_rate=implied_g,
        implied_vs_forward_delta=delta,
        wacc=wacc,
        terminal_growth_rate=params.terminal_growth_rate,
        fcf_seed=fcf_seed,
        fcf_seed_source=fcf_seed_source,
        interpretation=interpretation,
        verification_iv=verification_iv,
        verification_error_pct=verification_error_pct,
    )

    return ReverseDCFReport(
        result=result,
        params=params,
        current_price=price,
        ticker=sm.profile.ticker,
    )
