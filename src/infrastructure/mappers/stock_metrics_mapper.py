"""
stock_metrics_mapper.py
"""
from __future__ import annotations

import typing
from abc import abstractmethod
from dataclasses import is_dataclass
from typing import Dict, Any, Type, get_args, get_origin, Union

from domain.metrics.stock import StockMetrics
from .base_mapper import GenericMapper


class BaseStockMetricsMapper(GenericMapper):
    _CLASS_TO_FIELD_REF_MAP_CACHE: Dict[Type, Any] | None = None

    @classmethod
    def _class_to_field_map(cls) -> Dict[Type, Any]:
        if cls._CLASS_TO_FIELD_REF_MAP_CACHE is not None:
            return cls._CLASS_TO_FIELD_REF_MAP_CACHE

        mapping: Dict[Type, Any] = {}
        try:
            hints = typing.get_type_hints(StockMetrics)
        except Exception:
            hints = StockMetrics.__annotations__

        for field_name, field_type in hints.items():
            field_attr = getattr(StockMetrics, field_name, None)
            if field_attr is None:
                continue

            if is_dataclass(field_type):
                mapping[field_type] = field_attr
                continue

            if get_origin(field_type) is Union:
                inner = [t for t in get_args(field_type) if t is not type(None)]
                if len(inner) == 1 and is_dataclass(inner[0]):
                    mapping[inner[0]] = field_attr

        cls._CLASS_TO_FIELD_REF_MAP_CACHE = mapping
        return mapping

    @property
    def target_type(self) -> Type:
        return StockMetrics

    @property
    @abstractmethod
    def mapping(self) -> Dict[Any, GenericMapper]:
        raise NotImplementedError

    def __getitem__(self, field_reference: Any) -> GenericMapper:
        class_map = self._class_to_field_map()
        if isinstance(field_reference, type) and field_reference in class_map:
            field_reference = class_map[field_reference]

        try:
            sub_mapper = super().__getitem__(field_reference)
        except KeyError as exc:
            raise KeyError(
                f"Sub-mapper not found for key {field_reference!r}. "
                "Pass a StockMetrics field descriptor or a domain class "
                "registered in the mapper."
            ) from exc

        if not isinstance(sub_mapper, GenericMapper):
            raise TypeError(
                f"Value mapped to {field_reference!r} is not a GenericMapper. "
                f"Got {type(sub_mapper).__name__}."
            )

        return sub_mapper
