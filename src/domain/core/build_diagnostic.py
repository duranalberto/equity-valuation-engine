from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .missing import MissingReason


@dataclass(frozen=True)
class BuildDiagnostic:
    """
    Immutable record of a formula-level miss emitted by a domain builder.

    Produced by ``Valuation.build()`` and ``Ratios.build()`` when a derived
    field resolves to its zero/None default because one or more inputs were
    missing or mathematically invalid.

    ``model``  — domain class that owns the field, e.g. ``"Valuation"``.
    ``field``  — attribute name, e.g. ``"corporate_tax_rate"``.
    ``reason`` — categorised cause (see ``MissingReason``).
    ``detail`` — human-readable explanation for diagnostics output.
    """

    model:  str
    field:  str
    reason: MissingReason
    detail: Optional[str] = None