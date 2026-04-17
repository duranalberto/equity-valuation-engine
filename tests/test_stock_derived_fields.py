from __future__ import annotations

import pytest

from domain.core.missing import Missing
from domain.metrics.stock import BalanceSheet, CashFlow, Financials


def test_financials_derived_fields_are_populated_or_missing() -> None:
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


def test_financials_derived_fields_surface_missing_state() -> None:
    financials = Financials(
        revenue_ttm=None,
        ebit_ttm=None,
        ebt_ttm=None,
        tax_expense_ttm=None,
        interest_expense_ttm=None,
        gross_profit_ttm=None,
        operating_income_ttm=None,
        net_income_ttm=None,
        revenue_ttm_prev=None,
        net_income_ttm_prev=None,
        da_ttm=None,
    )

    assert isinstance(financials.gross_margin, Missing)
    assert financials.gross_margin.field == "gross_margin"
    assert isinstance(financials.ebitda_ttm, Missing)


def test_cash_flow_and_balance_sheet_derived_fields_surface_missing_state() -> None:
    cash_flow = CashFlow(
        operating_cf_ttm=None,
        capex_ttm=None,
        oper_cf_last_year=None,
        latest_annual_capex=None,
        oper_cf_last_quarter=None,
        latest_quarter_capex=None,
        dividends_paid_ttm=None,
        share_buybacks_ttm=None,
    )
    balance_sheet = BalanceSheet(
        total_debt=None,
        total_equity=None,
        cash_and_equivalents=None,
        total_assets=None,
        total_liabilities=None,
        current_assets=None,
        current_liabilities=None,
        inventory=None,
    )

    assert isinstance(cash_flow.fcf_ttm, Missing)
    assert isinstance(cash_flow.last_year_fcf, Missing)
    assert isinstance(cash_flow.last_quarter_fcf, Missing)
    assert isinstance(balance_sheet.current_ratio, Missing)
    assert isinstance(balance_sheet.quick_ratio, Missing)
