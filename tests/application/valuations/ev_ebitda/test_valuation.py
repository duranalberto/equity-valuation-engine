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

def test_ev_ebitda_formula_base_case() -> None:
    from application.valuations.ev_ebitda.valuation import ev_ebitda_valuation
    from domain.valuation.models.ev_ebitda import EVEBITDAParameters, EVEBITDAValuationInput

    metrics = _metrics(
        current_price=60.0,
        shares_outstanding=10,
        ebitda_ttm=100.0,
        total_debt=150.0,
        cash=50.0,
    )
    result = ev_ebitda_valuation(
        EVEBITDAValuationInput(
            stock_metrics=metrics,
            ebitda_multiple=8.0,
            params=EVEBITDAParameters(projection_years=1, margin_of_safety=0.0),
            scenario="Base",
        )
    )

    assert result.intrinsic_ev == pytest.approx(800.0)
    assert result.equity_value == pytest.approx(700.0)
    assert result.intrinsic_value_per_share == pytest.approx(70.0)
    assert result.total_debt == pytest.approx(150.0)
    assert result.cash_and_equivalents == pytest.approx(50.0)
