from __future__ import annotations

from typing import Dict, Type

from infrastructure.mappers.base_mapper import GenericMapper


class StockMetricsMapper:
    """
    Registry mapping every ``StockMetrics`` sub-model class to its
    ``GenericMapper``.

    Concrete loader implementations (e.g. ``YfinanceDataLoader``) subclass
    this and populate the registry with field descriptors appropriate to
    their data source.
    """

    def __init__(self) -> None:
        self._mappers: Dict[Type, GenericMapper] = {}

    def register(self, model_cls: Type, mapper: GenericMapper) -> None:
        self._mappers[model_cls] = mapper

    def __getitem__(self, model_cls: Type) -> GenericMapper:
        try:
            return self._mappers[model_cls]
        except KeyError as exc:
            raise KeyError(
                f"No mapper registered for {model_cls.__name__}. "
                "Did you forget to call register() for this class?"
            ) from exc

    def __contains__(self, model_cls: Type) -> bool:
        return model_cls in self._mappers
