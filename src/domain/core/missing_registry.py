from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from typing import List, Set

from .missing import Missing


@dataclass(frozen=True)
class FieldGap:
    model: str
    field: str
    missing: Missing

    @property
    def path(self) -> str:
        return self.field


class MissingRegistry:
    def __init__(self) -> None:
        self._gaps: List[FieldGap] = []
        self._seen: Set[int] = set()

    def scan(self, model: object, model_name: str | None = None) -> "MissingRegistry":
        self._scan(model, model_name=model_name, parent_path="")
        return self

    def _scan(self, model: object, *, model_name: str | None, parent_path: str) -> None:
        if not is_dataclass(model):
            return

        model_id = id(model)
        if model_id in self._seen:
            return
        self._seen.add(model_id)

        current_name = model_name or type(model).__name__

        for field in fields(model):
            value = getattr(model, field.name, None)
            field_path = f"{parent_path}.{field.name}" if parent_path else field.name

            if isinstance(value, Missing):
                self._gaps.append(
                    FieldGap(model=current_name, field=field_path, missing=value)
                )
                continue

            if is_dataclass(value):
                self._scan(value, model_name=type(value).__name__, parent_path=field_path)
                continue

            if value is None:
                continue

    @property
    def gaps(self) -> List[FieldGap]:
        return list(self._gaps)

    def gaps_for(self, model_name: str) -> List[FieldGap]:
        return [g for g in self._gaps if g.model == model_name or g.path.startswith(f"{model_name}.")]

    def report(self) -> str:
        if not self._gaps:
            return "No missing fields detected."
        return "\n".join(
            f"[{g.path}] {g.missing.reason.value}: {g.missing.detail}"
            for g in self._gaps
        )
