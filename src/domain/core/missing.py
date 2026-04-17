from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class MissingReason(Enum):
    DATA_SOURCE_GAP = "data_source_gap"
    NOT_REPORTED = "not_reported"
    NOT_APPLICABLE = "not_applicable"
    INSUFFICIENT_DATA = "insufficient_data"
    INVALID_INPUT = "invalid_input"


@dataclass(frozen=True)
class Missing:
    reason: MissingReason
    field: str
    detail: str = ""

    def __repr__(self) -> str:
        return f"Missing({self.field!r}: {self.reason.value})"

    @property
    def is_source_gap(self) -> bool:
        return self.reason == MissingReason.DATA_SOURCE_GAP

    @property
    def is_invalid_input(self) -> bool:
        return self.reason == MissingReason.INVALID_INPUT

    @property
    def is_derived_gap(self) -> bool:
        return not self.is_source_gap and not self.is_invalid_input
