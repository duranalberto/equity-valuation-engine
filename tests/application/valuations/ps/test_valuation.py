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

def test_ps_formula_base_scenario(monkeypatch) -> None:
    from application.valuations.ps import valuation as ps_valuation

    monkeypatch.setattr(
        ps_valuation,
        "get_multiple",
        lambda metrics, scenario: {"Bear": 2.0, "Base": 3.0, "Bull": 4.0}[scenario],
    )
    metrics = _metrics(
        current_price=25.0,
        shares_outstanding=20,
        market_cap=500.0,
        revenue_ttm=200.0,
    )

    report = ps_valuation.execute_ps_scenarios(metrics)
    result = report.scenarios["Base"]

    assert report.revenue_ttm == pytest.approx(200.0)
    assert result.ps_multiple_used == pytest.approx(3.0)
    assert result.intrinsic_market_cap == pytest.approx(600.0)
    assert result.intrinsic_value_per_share == pytest.approx(30.0)
    assert result.implied_revenue_multiple == pytest.approx(2.5)
