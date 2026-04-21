from types import SimpleNamespace

import pytest

from application.valuations.dcf.valuation import dcf_valuation
from application.valuations.dcf.validator import evaluate_dcf
from domain.valuation.models.dcf import DCFInputData, DCFParameters


def _make_stock_metrics(
    *,
    fcf_ttm: float,
    last_year_fcf: float,
    capex_spike_detected: bool = False,
    normalized_fcf: float | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        profile=SimpleNamespace(ticker="TEST", sector=None),
        cash_flow=SimpleNamespace(
            fcf_ttm=fcf_ttm,
            last_year_fcf=last_year_fcf,
            last_quarter_fcf=1.0,
            operating_cf_ttm=20.0,
        ),
        financials=SimpleNamespace(
            net_income_ttm=100.0,
            revenue_growth_rate=0.1,
        ),
        valuation=SimpleNamespace(
            capex_spike_detected=capex_spike_detected,
            normalized_fcf=normalized_fcf,
            cost_of_debt=0.05,
            corporate_tax_rate=0.2,
        ),
        balance_sheet=SimpleNamespace(
            total_debt=10.0,
            cash_and_equivalents=5.0,
            total_equity=20.0,
        ),
        market_data=SimpleNamespace(
            market_cap=100.0,
            beta=1.0,
            shares_outstanding=10.0,
            current_price=1.0,
            eps_ttm=1.0,
            pe_ttm=10.0,
        ),
    )


def test_dcf_valuation_returns_result_without_extra_constructor_field() -> None:
    stock_metrics = _make_stock_metrics(fcf_ttm=10.0, last_year_fcf=8.0)
    input_data = DCFInputData(
        stock_metrics=stock_metrics,
        growth_rates=[0.1, 0.1, 0.1],
        wacc=SimpleNamespace(wacc=0.1),
        params=DCFParameters(projection_years=3, margin_of_safety=0.25),
    )

    result = dcf_valuation(input_data)

    assert result.fcf_projections == pytest.approx([11.0, 12.1, 13.31])
    assert result.fcf_seed_source == "raw"
    assert result.intrinsic_value_per_share > 0


def test_dcf_valuation_marks_normalized_seed_when_capex_spike_exists() -> None:
    stock_metrics = _make_stock_metrics(
        fcf_ttm=-10.0,
        last_year_fcf=8.0,
        capex_spike_detected=True,
        normalized_fcf=25.0,
    )
    input_data = DCFInputData(
        stock_metrics=stock_metrics,
        growth_rates=[0.1, 0.1, 0.1],
        wacc=SimpleNamespace(wacc=0.1),
        params=DCFParameters(projection_years=3, margin_of_safety=0.25),
    )

    result = dcf_valuation(input_data)

    assert result.fcf_seed_source == "normalized"


def test_dcf_validator_allows_capex_spike_when_normalized_fcf_exists() -> None:
    stock_metrics = _make_stock_metrics(
        fcf_ttm=-10.0,
        last_year_fcf=8.0,
        capex_spike_detected=True,
        normalized_fcf=25.0,
    )

    result = evaluate_dcf(stock_metrics)

    assert result.is_suitable is True
    assert result.total_severity_score < 99
    assert any(f.name == "Capex Spike Detected" for f in result.factors)


def test_dcf_validator_blocks_dual_negative_fcf_without_normalization() -> None:
    stock_metrics = _make_stock_metrics(
        fcf_ttm=-10.0,
        last_year_fcf=-8.0,
        capex_spike_detected=True,
        normalized_fcf=None,
    )

    result = evaluate_dcf(stock_metrics)

    assert result.is_suitable is False
    assert result.total_severity_score == 99
