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

def test_nav_formula_base_scenario(monkeypatch) -> None:
    from application.valuations.nav import valuation as nav_valuation

    monkeypatch.setattr(
        nav_valuation,
        "get_haircut",
        lambda metrics, scenario: {"Bear": 0.7, "Base": 0.8, "Bull": 0.9}[scenario],
    )
    metrics = _metrics(
        current_price=50.0,
        shares_outstanding=10,
        total_assets=1000.0,
        total_liabilities=300.0,
        total_equity=700.0,
    )

    report = nav_valuation.execute_nav_scenarios(metrics)
    result = report.scenarios["Base"]

    assert result.asset_haircut_used == pytest.approx(0.8)
    assert result.adjusted_assets == pytest.approx(800.0)
    assert result.nav == pytest.approx(500.0)
    assert result.nav_per_share == pytest.approx(50.0)
    assert result.price_to_nav == pytest.approx(1.0)
    assert result.intrinsic_value_per_share == pytest.approx(result.nav_per_share)

def test_nav_uses_real_goodwill_and_intangibles_ratio(monkeypatch) -> None:
    from application.valuations.nav import valuation as nav_valuation

    monkeypatch.setattr(
        nav_valuation,
        "get_haircut",
        lambda metrics, scenario: {"Bear": 0.7, "Base": 0.8, "Bull": 0.9}[scenario],
    )
    monkeypatch.setattr(nav_valuation, "get_intangible_cap", lambda metrics: 0.50)
    metrics = _metrics(
        current_price=50.0,
        shares_outstanding=10,
        total_assets=1000.0,
        total_liabilities=300.0,
        total_equity=700.0,
    )
    metrics.balance_sheet.goodwill_and_intangibles = 600.0

    report = nav_valuation.execute_nav_scenarios(metrics)
    result = report.scenarios["Base"]

    assert report.goodwill_and_intangibles == pytest.approx(600.0)
    assert report.intangible_asset_ratio == pytest.approx(0.60)
    assert result.intangible_asset_ratio == pytest.approx(0.60)
    assert result.intangible_warning is True
