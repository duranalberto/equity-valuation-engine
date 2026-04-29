from __future__ import annotations

import pytest

from domain.core.missing import MissingReason
from domain.core.missing_registry import MissingValueRegistry
from domain.metrics.stock import (
    BalanceSheet,
    CashFlow,
    CompanyProfile,
    Financials,
    HistoricalData,
    MarketData,
    StockMetrics,
    Valuation,
)


def test_financials_derived_fields_are_populated() -> None:
    financials = Financials(
        revenue_ttm=200.0,
        ebit_ttm=40.0,
        ebt_ttm=35.0,
        tax_expense_ttm=7.0,
        interest_expense_ttm=2.0,
        gross_profit_ttm=120.0,
        operating_income_ttm=50.0,
        net_income_ttm=28.0,
        revenue_ttm_prev=160.0,
        net_income_ttm_prev=20.0,
        da_ttm=10.0,
    )

    assert financials.revenue_growth_rate == 0.25
    assert financials.net_income_growth == pytest.approx(0.4)
    assert financials.gross_margin == 0.6
    assert financials.operating_margin == 0.25
    assert financials.net_margin == 0.14
    assert financials.ebitda_ttm == 50.0


def test_direct_zero_inputs_produce_numeric_defaults() -> None:
    financials = Financials()
    cash_flow = CashFlow()
    balance_sheet = BalanceSheet()

    assert financials.revenue_growth_rate == 0.0
    assert financials.net_income_growth == 0.0
    assert financials.gross_margin == 0.0
    assert financials.operating_margin == 0.0
    assert financials.net_margin == 0.0
    assert financials.ebitda_ttm == 0.0
    assert cash_flow.fcf_ttm == 0.0
    assert cash_flow.last_year_fcf == 0.0
    assert cash_flow.last_quarter_fcf == 0.0
    assert balance_sheet.current_ratio == 0.0
    assert balance_sheet.quick_ratio == 0.0
    assert balance_sheet.goodwill_and_intangibles == 0.0


def test_balance_sheet_derives_goodwill_and_intangibles_from_components() -> None:
    balance_sheet = BalanceSheet(
        total_assets=100.0,
        goodwill=25.0,
        other_intangible_assets=15.0,
    )

    assert balance_sheet.goodwill_and_intangibles == 40.0


def test_invalid_derived_states_are_reported_as_build_diagnostics() -> None:
    stock = StockMetrics(
        profile=CompanyProfile(ticker="ZERO"),
        financials=Financials(),
        cash_flow=CashFlow(),
        balance_sheet=BalanceSheet(),
        market_data=MarketData(
            current_price=10.0,
            shares_outstanding=1,
            market_cap=10.0,
        ),
        valuation=Valuation(),
        historical_data=HistoricalData(),
    ).finalize()

    diagnostics = {(diag.model, diag.field, diag.reason) for diag in stock._diagnostics}

    assert ("Valuation", "price_to_sales", MissingReason.ZERO_DENOMINATOR) in diagnostics
    assert ("Ratios", "price_to_fcf", MissingReason.ZERO_DENOMINATOR) in diagnostics
    assert ("Ratios", "fcf_yield", MissingReason.ZERO_DENOMINATOR) in diagnostics
    assert ("Ratios", "ev_ebitda", MissingReason.ZERO_DENOMINATOR) in diagnostics


def test_build_diagnostics_can_be_recorded_in_missing_registry() -> None:
    stock = StockMetrics(
        profile=CompanyProfile(ticker="ZERO"),
        financials=Financials(),
        cash_flow=CashFlow(),
        balance_sheet=BalanceSheet(),
        market_data=MarketData(
            current_price=10.0,
            shares_outstanding=1,
            market_cap=10.0,
        ),
        valuation=Valuation(),
        historical_data=HistoricalData(),
    ).finalize()
    registry = MissingValueRegistry()

    for diag in stock._diagnostics:
        registry.record_derived(diag.model, diag.field, diag.reason, diag.detail)

    assert registry.has_missing_field("Valuation", "price_to_sales")
    assert registry.has_missing_field("Ratios", "price_to_fcf")
    assert registry.get("Ratios", "price_to_fcf").detail == "fcf_ttm is zero"
