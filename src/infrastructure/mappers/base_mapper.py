from abc import ABC, abstractmethod
from typing import Dict, Any, get_origin, get_args, get_type_hints, Union, Type
from enum import Enum
from dataclasses import is_dataclass


class GenericMapper(ABC):

    def __init__(self):
        self.validate()

    @property
    @abstractmethod
    def target_type(self) -> type:
        raise NotImplementedError

    @property
    @abstractmethod
    def mapping(self) -> Dict[Any, Any]:
        raise NotImplementedError

    def _normalize_key(self, key: Any) -> str:
        if isinstance(key, str):
            return key

        cls = self.target_type

        if issubclass(cls, Enum):
            if isinstance(key, cls):
                return key
            raise ValueError(
                f"Invalid Enum mapping key: {key!r}. Expected member of {cls.__name__}."
            )

        if is_dataclass(cls):
            for name, field in cls.__dataclass_fields__.items():
                if key is field:
                    return name

            if isinstance(key, Enum):
                raise ValueError(
                    f"Invalid mapping key {key!r}: Enum values cannot be used as keys "
                    f"in CLASS MODE. Use the dataclass field instead."
                )

        raise ValueError(f"Invalid mapping key: {key!r}")

    @property
    def normalized_mapping(self) -> Dict[str, Any]:
        return {self._normalize_key(k): v for k, v in self.mapping.items()}

    def validate(self) -> None:
        cls = self.target_type

        if issubclass(cls, Enum):
            enum_keys = set(cls)
            mapping_keys = set(self.mapping.keys())
            extra = mapping_keys - enum_keys
            missing = enum_keys - mapping_keys
            if extra:
                raise ValueError(f"Invalid Enum keys for mapper of {cls.__name__}: {extra}")
            if missing:
                raise ValueError(f"Missing Enum keys for mapper of {cls.__name__}: {missing}")
            self._validate_unique_values()
            return

        domain = self.extract_domain(cls)
        required_fields = set(domain.keys())
        mapping_keys = set(self.normalized_mapping.keys())

        extra = mapping_keys - required_fields
        if extra:
            raise ValueError(f"Mapper has invalid field names: {extra}")

        missing_required = {
            key for key in required_fields - mapping_keys
            if not self.is_optional_type(domain[key])
        }
        if missing_required:
            raise ValueError(f"Mapper missing required fields: {missing_required}")

        self._validate_unique_values()

    def _validate_unique_values(self) -> None:
        values = list(self.normalized_mapping.values())
        duplicates = {v for v in values if values.count(v) > 1}
        if duplicates:
            raise ValueError(f"Mapper has duplicated output values: {duplicates}")

    def __getitem__(self, key: Any) -> Any:
        return self.normalized_mapping[self._normalize_key(key)]

    def items(self):
        return self.normalized_mapping.items()

    def get_key_from_value(self, value: Any) -> str:
        for k, v in self.normalized_mapping.items():
            if isinstance(v, str) and isinstance(value, str):
                if v.lower() == value.lower():
                    return k
            else:
                if v == value:
                    return k
        raise KeyError(f"Value not found in mapper: {value!r}")

    @staticmethod
    def is_optional_type(t: Any) -> bool:
        return get_origin(t) is Union and type(None) in get_args(t)

    @staticmethod
    def extract_domain(cls: type) -> Dict[str, Any]:
        try:
            hints = get_type_hints(cls)
            if hints:
                return hints
        except Exception:
            pass
        ann = getattr(cls, "__annotations__", None)
        if not ann:
            raise TypeError(f"Class {cls.__name__} has no type annotations.")
        return ann
