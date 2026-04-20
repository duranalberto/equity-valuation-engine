from __future__ import annotations

from typing import Any, Dict, Generic, Iterator, Type, TypeVar

T = TypeVar("T")


class GenericMapper(Generic[T]):
    """
    Ordered field-definition container for a single domain class.

    Iterating over a ``GenericMapper`` yields ``(field_name, field_descriptor)``
    pairs in the order they were registered.
    """

    def __init__(self, target_type: Type[T], fields: Dict[str, Any]) -> None:
        self.target_type = target_type
        self._fields:    Dict[str, Any] = dict(fields)

    def __getitem__(self, key: str) -> Any:
        return self._fields[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._fields)

    def items(self):
        return self._fields.items()

    def keys(self):
        return self._fields.keys()

    def values(self):
        return self._fields.values()

    def __contains__(self, key: object) -> bool:
        return key in self._fields

    def __len__(self) -> int:
        return len(self._fields)
