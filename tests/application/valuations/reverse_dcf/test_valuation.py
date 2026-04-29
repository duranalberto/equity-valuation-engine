from __future__ import annotations

from types import SimpleNamespace

import pytest

def _metrics(
    *,
    ticker: str = "TST",
    current_price: float = 50.0,
    shares_outstanding: int = 10,
    market_cap: float = 500.0,
    beta: float = 1.0,
    revenue_ttm: float = 0.0,
    ebitda_ttm: float = 0.0,
    total_debt: float = 0.0,
    cash: float = 0.0,
    total_assets: float = 0.0,
    total_liabilities: float = 0.0,
    total_equity: float = 0.0,
    fcf_ttm: float = 0.0,
    cost_of_debt: float = 0.0,
    tax_rate: float = 0.0,
    forward_growth_rate: float = 0.0,
):
    return SimpleNamespace(
        profile=SimpleNamespace(ticker=ticker, sector=SimpleNamespace(value="technology")),
        financials=SimpleNamespace(revenue_ttm=revenue_ttm, ebitda_ttm=ebitda_ttm),
        balance_sheet=SimpleNamespace(
            total_debt=total_debt,
            cash_and_equivalents=cash,
            total_assets=total_assets,
            total_liabilities=total_liabilities,
            total_equity=total_equity,
        ),
        market_data=SimpleNamespace(
            current_price=current_price,
            shares_outstanding=shares_outstanding,
            market_cap=market_cap,
            beta=beta,
        ),
        cash_flow=SimpleNamespace(fcf_ttm=fcf_ttm),
        valuation=SimpleNamespace(
            cost_of_debt=cost_of_debt,
            corporate_tax_rate=tax_rate,
            forward_growth_rate=forward_growth_rate,
            normalized_fcf=None,
            capex_spike_detected=False,
        ),
    )

def test_reverse_dcf_verifies_implied_growth_against_current_price() -> None:
    from application.valuations.reverse_dcf.valuation import solve_reverse_dcf
    from domain.valuation.models.reverse_dcf import ReverseDCFParameters

    metrics = _metrics(
        current_price=20.0,
        shares_outstanding=10,
        market_cap=200.0,
        beta=1.0,
        total_debt=0.0,
        cash=0.0,
        fcf_ttm=10.0,
        cost_of_debt=0.0,
        tax_rate=0.0,
        forward_growth_rate=0.05,
    )
    params = ReverseDCFParameters(
        projection_years=5,
        margin_of_safety=0.0,
        risk_free_rate=0.04,
        market_risk_premium=0.06,
        terminal_growth_rate=0.02,
        search_low=-0.10,
        search_high=0.60,
    )

    report = solve_reverse_dcf(metrics, params=params)

    assert report.result.verification_iv == pytest.approx(20.0, rel=0.01)
    assert report.result.verification_error_pct is not None
    assert report.result.verification_error_pct <= 0.01
