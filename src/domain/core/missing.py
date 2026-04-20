from dataclasses import dataclass
from enum import Enum
from typing import Optional


class MissingReason(Enum):
    NOT_IN_SOURCE     = "not_in_source"      # yfinance row absent or all-NaN
    ZERO_DENOMINATOR  = "zero_denominator"   # safe_div returned None because denom == 0
    INSUFFICIENT_DATA = "insufficient_data"  # < N data points for CAGR, median PE, etc.
    DERIVED_FAILED    = "derived_failed"     # component(s) zero/missing; formula unusable
    NOT_APPLICABLE    = "not_applicable"     # field meaningless for this instrument type


@dataclass(frozen=True)
class MissingField:
    """
    Immutable record of a single field that could not be populated.

    ``model``  — domain class name, e.g. ``"Financials"``.
    ``field``  — attribute name on that class, e.g. ``"ebitda_ttm"``.
    ``reason`` — why the value is absent (see ``MissingReason``).
    ``detail`` — optional human-readable context for diagnostics.
    """

    model:  str
    field:  str
    reason: MissingReason
    detail: Optional[str] = None
