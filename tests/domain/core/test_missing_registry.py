from __future__ import annotations

from domain.core.missing import MissingField, MissingReason
from domain.core.missing_registry import MissingValueRegistry


def test_missing_registry_records_source_level_misses() -> None:
    registry = MissingValueRegistry()

    registry.record(
        "Financials",
        "revenue_ttm",
        MissingReason.NOT_IN_SOURCE,
        "No data returned for label(s): Total Revenue",
    )

    entry = registry.get("Financials", "revenue_ttm")

    assert entry == MissingField(
        "Financials",
        "revenue_ttm",
        MissingReason.NOT_IN_SOURCE,
        "No data returned for label(s): Total Revenue",
    )
    assert registry.has_missing_field("Financials", "revenue_ttm")
    assert registry.has_missing("Financials")
    assert bool(registry)
    assert len(registry) == 1


def test_missing_registry_records_derived_misses() -> None:
    registry = MissingValueRegistry()

    registry.record_derived(
        "Ratios",
        "price_to_fcf",
        MissingReason.ZERO_DENOMINATOR,
        "fcf_ttm is zero",
    )

    entry = registry.get("Ratios", "price_to_fcf")

    assert entry is not None
    assert entry.model == "Ratios"
    assert entry.field == "price_to_fcf"
    assert entry.reason is MissingReason.ZERO_DENOMINATOR
    assert entry.detail == "fcf_ttm is zero"
    assert registry.has_missing("Ratios")


def test_missing_registry_queries_and_summary_use_all_entries() -> None:
    registry = MissingValueRegistry()
    registry.record("Financials", "revenue_ttm", MissingReason.NOT_IN_SOURCE)
    registry.record("Financials", "ebit_ttm", MissingReason.NOT_IN_SOURCE)
    registry.record_derived("Ratios", "ev_ebitda", MissingReason.ZERO_DENOMINATOR)

    assert registry.get("Financials", "missing_field") is None
    assert not registry.has_missing_field("Financials", "missing_field")
    assert not registry.has_missing("MarketData")
    assert registry.summary() == {
        "Financials": ["revenue_ttm", "ebit_ttm"],
        "Ratios": ["ev_ebitda"],
    }
    assert [entry.field for entry in registry.for_model("Financials")] == [
        "revenue_ttm",
        "ebit_ttm",
    ]


def test_missing_registry_iteration_preserves_raw_then_derived_order() -> None:
    registry = MissingValueRegistry()
    registry.record("Financials", "revenue_ttm", MissingReason.NOT_IN_SOURCE)
    registry.record_derived("Valuation", "price_to_sales", MissingReason.ZERO_DENOMINATOR)
    registry.record("CashFlow", "fcf_ttm", MissingReason.NOT_IN_SOURCE)
    registry.record_derived("Ratios", "price_to_fcf", MissingReason.ZERO_DENOMINATOR)

    assert [(entry.model, entry.field) for entry in registry] == [
        ("Financials", "revenue_ttm"),
        ("CashFlow", "fcf_ttm"),
        ("Valuation", "price_to_sales"),
        ("Ratios", "price_to_fcf"),
    ]
    assert len(registry) == 4


def test_empty_missing_registry_is_falsey() -> None:
    registry = MissingValueRegistry()

    assert not registry
    assert len(registry) == 0
    assert not registry.has_missing()
    assert registry.summary() == {}
    assert registry.for_model("Financials") == []
