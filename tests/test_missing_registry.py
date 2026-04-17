from __future__ import annotations

from dataclasses import dataclass

from domain.core.missing import Missing, MissingReason
from domain.core.missing_registry import MissingRegistry
from domain.metrics.stock import BalanceSheet, CashFlow, Financials


@dataclass
class Child:
    alpha: float | Missing | None = None
    beta: float | Missing | None = None


@dataclass
class Parent:
    child: Child | None = None
    sibling: Child | None = None


def test_missing_registry_reports_nested_paths() -> None:
    child = Child(alpha=Missing(MissingReason.DATA_SOURCE_GAP, "alpha", "no source"))
    parent = Parent(child=child)

    registry = MissingRegistry().scan(parent)

    assert [gap.path for gap in registry.gaps] == ["child.alpha"]
    assert registry.report() == "[child.alpha] data_source_gap: no source"


def test_missing_registry_deduplicates_shared_objects() -> None:
    shared = Child(alpha=Missing(MissingReason.INSUFFICIENT_DATA, "alpha", "shared"))
    parent = Parent(child=shared, sibling=shared)

    registry = MissingRegistry().scan(parent)

    assert [gap.path for gap in registry.gaps] == ["child.alpha"]


def test_missing_registry_scans_attached_companions() -> None:
    financials = Financials(
        revenue_ttm=100.0,
        ebit_ttm=10.0,
        ebt_ttm=10.0,
        tax_expense_ttm=2.0,
        interest_expense_ttm=1.0,
        gross_profit_ttm=50.0,
        operating_income_ttm=20.0,
        net_income_ttm=12.0,
        revenue_ttm_prev=90.0,
        net_income_ttm_prev=11.0,
        da_ttm=5.0,
    )
    balance_sheet = BalanceSheet(
        total_debt=100.0,
        total_equity=200.0,
        cash_and_equivalents=50.0,
        total_assets=400.0,
        total_liabilities=150.0,
        current_assets=80.0,
        current_liabilities=40.0,
        inventory=10.0,
    )
    cash_flow = CashFlow(
        operating_cf_ttm=120.0,
        capex_ttm=20.0,
        oper_cf_last_year=100.0,
        latest_annual_capex=15.0,
        oper_cf_last_quarter=30.0,
        latest_quarter_capex=5.0,
        dividends_paid_ttm=0.0,
        share_buybacks_ttm=0.0,
    )

    financials.history = Child(alpha=Missing(MissingReason.NOT_REPORTED, "history", "loaded later"))
    balance_sheet.history = Child(alpha=Missing(MissingReason.INVALID_INPUT, "history", "bad input"))
    cash_flow.history = Child(alpha=Missing(MissingReason.NOT_APPLICABLE, "history", "n/a"))

    registry = MissingRegistry().scan(financials).scan(balance_sheet).scan(cash_flow)

    assert any(g.path == "history.alpha" or g.path.endswith(".history.alpha") for g in registry.gaps)


def test_missing_registry_ignores_none_values() -> None:
    registry = MissingRegistry().scan(Parent(child=Child(alpha=None), sibling=None))

    assert registry.gaps == []
