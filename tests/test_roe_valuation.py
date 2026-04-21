from types import SimpleNamespace

import pytest

from application.valuations.roe.valuation import roe_valuation
from domain.valuation.models.roe import ROEParameters, ROEValuationInput


def test_roe_valuation_equity_per_share_progression_starts_per_share() -> None:
    stock_metrics = SimpleNamespace(
        balance_sheet=SimpleNamespace(total_equity=1000.0),
        market_data=SimpleNamespace(shares_outstanding=100.0, current_price=10.0),
        ratios=SimpleNamespace(return_on_equity=0.2),
    )
    params = ROEParameters(projection_years=3, margin_of_safety=0.25, discount_rate=0.1)
    roe_input = ROEValuationInput(
        stock_metrics=stock_metrics,
        dividend_rate_per_share=1.0,
        growth_rates=[0.1, 0.1, 0.1],
        params=params,
    )

    result = roe_valuation(roe_input)

    assert result.shareholders_equity_progression == pytest.approx([11.0, 12.1, 13.31])


def test_roe_valuation_discounts_first_year_cash_flow() -> None:
    stock_metrics = SimpleNamespace(
        balance_sheet=SimpleNamespace(total_equity=1000.0),
        market_data=SimpleNamespace(shares_outstanding=100.0, current_price=10.0),
        ratios=SimpleNamespace(return_on_equity=0.2),
    )
    params = ROEParameters(projection_years=1, margin_of_safety=0.25, discount_rate=0.1)
    roe_input = ROEValuationInput(
        stock_metrics=stock_metrics,
        dividend_rate_per_share=1.0,
        growth_rates=[0.1],
        params=params,
    )

    result = roe_valuation(roe_input)

    assert result.dividend_progression == pytest.approx([1.1])
    assert result.npv_dividend_progression == pytest.approx([1.0])
