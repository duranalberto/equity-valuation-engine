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

def test_ddm_formula_discounted_dividends_and_terminal_value() -> None:
    from application.valuations.ddm.valuation import ddm_valuation
    from domain.valuation.models.ddm import DDMParameters

    metrics = _metrics(current_price=40.0, beta=1.0)
    growth_rates = [0.05, 0.05, 0.05]
    params = DDMParameters(
        projection_years=3,
        margin_of_safety=0.0,
        risk_free_rate=0.04,
        market_risk_premium=0.06,
        terminal_growth_rate=0.03,
    )

    result = ddm_valuation(
        stock_metrics=metrics,
        growth_rates=growth_rates,
        params=params,
        dps_ttm=2.0,
        scenario="Base",
    )

    required_return = 0.10
    dividend_1 = 2.0 * 1.05
    dividend_2 = dividend_1 * 1.05
    dividend_3 = dividend_2 * 1.05
    terminal_dividend = dividend_3 * 1.03
    terminal_value = terminal_dividend / (required_return - 0.03)
    pv_dividends = (
        dividend_1 / 1.10
        + dividend_2 / 1.10**2
        + dividend_3 / 1.10**3
    )
    pv_terminal_value = terminal_value / 1.10**3

    assert result.required_return == pytest.approx(required_return)
    assert result.dividend_progression == pytest.approx([dividend_1, dividend_2, dividend_3])
    assert result.terminal_dividend == pytest.approx(terminal_dividend)
    assert result.terminal_value == pytest.approx(terminal_value)
    assert result.pv_dividends == pytest.approx(pv_dividends)
    assert result.pv_terminal_value == pytest.approx(pv_terminal_value)
    assert result.intrinsic_value_per_share == pytest.approx(pv_dividends + pv_terminal_value)
    assert result.dividend_yield_implied == pytest.approx(
        dividend_1 / result.intrinsic_value_per_share
    )

def test_ddm_execute_uses_fallback_growth_when_history_lacks_dividend_series() -> None:
    from application.valuations.ddm.valuation import execute_ddm_scenarios
    from domain.valuation.models.ddm import DDMParameters

    metrics = _metrics(current_price=40.0, shares_outstanding=10, beta=1.0)
    metrics.cash_flow.dividends_paid_ttm = -20.0
    metrics.cash_flow.history = SimpleNamespace(fcf_annual=[1.0, 2.0, 3.0])
    params = DDMParameters(
        projection_years=3,
        margin_of_safety=0.0,
        risk_free_rate=0.04,
        market_risk_premium=0.06,
        terminal_growth_rate=0.03,
    )

    report = execute_ddm_scenarios(metrics, params=params)

    assert report.dividend_growth_rate == pytest.approx(0.03)
    assert report.scenarios["Base"].growth_rates == pytest.approx([0.03, 0.03, 0.03])

def test_ddm_execute_uses_real_dividend_history_and_caps_growth() -> None:
    from application.valuations.ddm.valuation import execute_ddm_scenarios
    from domain.metrics.history import CashFlowHistory
    from domain.valuation.models.ddm import DDMParameters

    metrics = _metrics(current_price=40.0, shares_outstanding=10, beta=1.0)
    metrics.cash_flow.dividends_paid_ttm = -20.0
    metrics.cash_flow.history = CashFlowHistory(dividends_paid_annual=[-1.0, -2.0, -4.0])
    params = DDMParameters(
        projection_years=2,
        margin_of_safety=0.0,
        risk_free_rate=0.04,
        market_risk_premium=0.06,
        terminal_growth_rate=0.03,
    )

    report = execute_ddm_scenarios(metrics, params=params)

    assert report.dividend_growth_rate == pytest.approx(0.15)
    assert report.scenarios["Base"].growth_rates == pytest.approx([0.15, 0.15])

def test_ddm_dividend_growth_scenarios_apply_mos_and_clamps(monkeypatch) -> None:
    from application.valuations.ddm import valuation as ddm_valuation
    from domain.valuation.models.ddm import DDMParameters

    class ScenarioConfig:
        def get_nested_float(self, section, scenario, sector, default):
            assert section == "scenario_multipliers"
            return {"Bear": 0.5, "Base": 1.0, "Bull": 2.0}[scenario]

    monkeypatch.setattr(
        ddm_valuation,
        "load_valuation_config",
        lambda name: ScenarioConfig(),
        raising=False,
    )
    metrics = _metrics()
    params = DDMParameters(
        projection_years=4,
        margin_of_safety=0.20,
        risk_free_rate=0.04,
        market_risk_premium=0.06,
        terminal_growth_rate=0.03,
    )

    scenarios = ddm_valuation._build_dividend_growth_scenarios(
        metrics,
        params,
        dividend_growth=0.15,
    )

    assert set(scenarios) == {"Bear", "Base", "Bull"}
    assert scenarios["Bear"] == pytest.approx([0.06] * 4)
    assert scenarios["Base"] == pytest.approx([0.15] * 4)
    assert scenarios["Bull"] == pytest.approx([0.20] * 4)

def test_ddm_valuation_module_has_no_dead_growth_scenario_imports() -> None:
    import inspect
    from application.valuations.ddm import valuation as ddm_valuation

    source = inspect.getsource(ddm_valuation)

    assert "generate_growth_scenarios" not in source
    assert "import random" not in source
