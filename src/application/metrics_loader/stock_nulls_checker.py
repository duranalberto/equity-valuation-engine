from __future__ import annotations

from typing import Optional

from domain.core.missing import MissingReason
from domain.core.missing_registry import MissingValueRegistry

_REASON_LABEL: dict[MissingReason, str] = {
    MissingReason.NOT_IN_SOURCE:     "NOT IN SOURCE",
    MissingReason.ZERO_DENOMINATOR:  "ZERO DENOMINATOR",
    MissingReason.INSUFFICIENT_DATA: "INSUFFICIENT DATA",
    MissingReason.DERIVED_FAILED:    "DERIVED FAILED",
    MissingReason.NOT_APPLICABLE:    "NOT APPLICABLE",
}

_SEVERITY_ORDER: list[MissingReason] = [
    MissingReason.NOT_IN_SOURCE,
    MissingReason.DERIVED_FAILED,
    MissingReason.ZERO_DENOMINATOR,
    MissingReason.INSUFFICIENT_DATA,
    MissingReason.NOT_APPLICABLE,
]


def evaluate_nulls(
    registry: MissingValueRegistry,
    model_filter: Optional[str] = None,
) -> None:
    """
    Print a formatted diagnostic report for every recorded missing field.

    Parameters
    ----------
    registry : MissingValueRegistry
        The registry produced during ``MetricsLoader.build_stock_metrics()``.
    model_filter : str, optional
        When given, only entries for the named model are printed.
        E.g. ``"Financials"`` or ``"Valuation"``.
    """
    if not registry:
        print("No missing values recorded — all fields resolved successfully.")
        return

    models_to_print = (
        [model_filter]
        if model_filter is not None
        else sorted(registry.summary().keys())
    )

    for model in models_to_print:
        entries = registry.for_model(model)
        if not entries:
            continue

        print(f"\n--- {model} ({len(entries)} missing) ---")

        sorted_entries = sorted(
            entries,
            key=lambda e: _SEVERITY_ORDER.index(e.reason),
        )
        for entry in sorted_entries:
            label  = _REASON_LABEL.get(entry.reason, entry.reason.value)
            detail = f" — {entry.detail}" if entry.detail else ""
            print(f"  [{label}] {entry.field}{detail}")


def summarise_nulls(registry: MissingValueRegistry) -> dict[str, int]:
    """
    Return a ``{reason_value: count}`` breakdown across all entries.

    Useful for metrics/logging rather than human-readable output.
    """
    counts: dict[str, int] = {}
    for entry in registry:
        key = entry.reason.value
        counts[key] = counts.get(key, 0) + 1
    return counts
