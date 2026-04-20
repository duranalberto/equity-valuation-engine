from __future__ import annotations

from typing import Dict, Iterator, List, Optional

from .missing import MissingField, MissingReason


class MissingValueRegistry:
    """
    Collects ``MissingField`` events emitted during a single
    ``MetricsLoader.build_stock_metrics()`` call.

    Lifecycle
    ---------
    Create one instance before calling ``MetricsLoader``, pass it in, inspect
    it afterwards.  Never reuse across builds.

    Two internal buckets
    --------------------
    ``_raw``     — source-level misses recorded by ``get_from_field()`` when
                   the data loader returns ``None``.  Stable after the loader
                   phase completes.

    ``_derived`` — formula-level misses recorded by ``_post_build_audit()``
                   after ``_rebuild_derived()`` has run for the final time.
                   Cleared by ``clear_derived()`` before the second rebuild
                   pass so stale first-pass entries do not pollute the final
                   registry state.
    """

    def __init__(self) -> None:
        self._raw:     List[MissingField] = []
        self._derived: List[MissingField] = []

    def record(
        self,
        model:  str,
        field:  str,
        reason: MissingReason,
        detail: Optional[str] = None,
    ) -> None:
        """Record a source-level miss (called from ``_get_field_value``)."""
        self._raw.append(MissingField(model, field, reason, detail))

    def record_derived(
        self,
        model:  str,
        field:  str,
        reason: MissingReason,
        detail: Optional[str] = None,
    ) -> None:
        """Record a formula-level miss (called from ``_post_build_audit``)."""
        self._derived.append(MissingField(model, field, reason, detail))

    def clear_derived(self) -> None:
        """
        Discard all derived-field entries.

        Called by ``MetricsLoader.build_stock_metrics()`` immediately before
        the second ``_rebuild_derived()`` pass so stale first-pass entries
        (computed without history) do not appear in the final registry.
        """
        self._derived.clear()

    def get(self, model: str, field: str) -> Optional[MissingField]:
        """Return the first matching entry across both buckets, or ``None``."""
        for entry in self._all():
            if entry.model == model and entry.field == field:
                return entry
        return None

    def has_missing_field(self, model: str, field: str) -> bool:
        """Return ``True`` when the (model, field) pair has a recorded miss."""
        return self.get(model, field) is not None

    def has_missing(self, model: Optional[str] = None) -> bool:
        """
        Return ``True`` when any entry exists.

        When ``model`` is given, restricts the check to that model name.
        """
        entries = self._all()
        if model is None:
            return bool(entries)
        return any(e.model == model for e in entries)

    def for_model(self, model: str) -> List[MissingField]:
        """Return all entries for the given model, preserving insertion order."""
        return [e for e in self._all() if e.model == model]

    def summary(self) -> Dict[str, List[str]]:
        """
        Group missing field names by model.

        Returns a ``{model_name: [field_name, ...]}`` mapping useful for
        logging and diagnostic output.
        """
        result: Dict[str, List[str]] = {}
        for entry in self._all():
            result.setdefault(entry.model, []).append(entry.field)
        return result

    def __iter__(self) -> Iterator[MissingField]:
        return iter(self._all())

    def __len__(self) -> int:
        return len(self._raw) + len(self._derived)

    def __bool__(self) -> bool:
        return bool(self._raw or self._derived)

    def _all(self) -> List[MissingField]:
        return [*self._raw, *self._derived]
