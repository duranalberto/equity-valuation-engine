from typing import Dict, Any, Type, get_args, get_origin, Union
from abc import abstractmethod
from dataclasses import is_dataclass
from domain.metrics.stock import StockMetrics
from .base_mapper import GenericMapper


class BaseStockMetricsMapper(GenericMapper):
    
    @staticmethod
    def _get_class_to_field_map(cls: Type) -> Dict[Type, Any]:
        if not is_dataclass(cls):
            return {}
        
        mapping = {}
        for field_name, field_type in getattr(cls, "__annotations__", {}).items():
            field_attr = getattr(cls, field_name)
            
            if get_origin(field_type) is Union:
                field_types = [t for t in get_args(field_type) if t is not type(None)]
                if len(field_types) == 1 and is_dataclass(field_types[0]):
                    mapping[field_types[0]] = field_attr
            elif is_dataclass(field_type):
                mapping[field_type] = field_attr
                
        return mapping

    _CLASS_TO_FIELD_REF_MAP: Dict[Type, Any] = _get_class_to_field_map(StockMetrics)

    @property
    def target_type(self) -> Type:
        return StockMetrics

    @property
    @abstractmethod
    def mapping(self) -> Dict[Any, GenericMapper]:
        raise NotImplementedError

    def __getitem__(self, field_reference: Any) -> GenericMapper:
        
        if isinstance(field_reference, type):
            if field_reference in self._CLASS_TO_FIELD_REF_MAP:
                field_reference = self._CLASS_TO_FIELD_REF_MAP[field_reference]
            else:
                pass
        
        try:
            sub_mapper = super().__getitem__(field_reference)
        except KeyError as e:
            if isinstance(field_reference, type) and field_reference in self._CLASS_TO_FIELD_REF_MAP:
                raise KeyError(f"Mapper logic error: Could not find field {field_reference.__name__} in mapping.") from e
            raise KeyError(f"Sub-mapper not found or invalid key: {field_reference!r}. Expected a StockMetrics field reference.") from e
            
        if not isinstance(sub_mapper, GenericMapper):
            raise TypeError(
                f"Value mapped to {field_reference!r} is not a GenericMapper instance. "
                f"Got {type(sub_mapper).__name__}."
            )
            
        return sub_mapper

