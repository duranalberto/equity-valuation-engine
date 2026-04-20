from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from domain.core.enums import Sectors

logger = logging.getLogger(__name__)

_CONFIG_ROOT = Path(__file__).parent


class ValuationConfig:
    """Thin, read-only wrapper around a YAML config dict."""

    def __init__(self, data: Dict[str, Any], source: Path) -> None:
        self._data   = data
        self._source = source

    def get_float(
        self,
        section: str,
        sector: Optional[Sectors],
        default: float,
    ) -> float:
        value = self._lookup(section, sector)
        if value is None:
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            logger.warning(
                "Config %s[%s][%s] = %r is not a valid float; using default %s.",
                self._source.name, section, self._sector_key(sector), value, default,
            )
            return default

    def get_int(
        self,
        section: str,
        sector: Optional[Sectors],
        default: int,
    ) -> int:
        value = self._lookup(section, sector)
        if value is None:
            return default
        try:
            return int(value)
        except (TypeError, ValueError):
            logger.warning(
                "Config %s[%s][%s] = %r is not a valid int; using default %s.",
                self._source.name, section, self._sector_key(sector), value, default,
            )
            return default

    def get_nested_float(
        self,
        outer_key: str,
        inner_key: str,
        sector: Optional[Sectors],
        default: float,
    ) -> float:
        outer = self._data.get(outer_key)
        if not isinstance(outer, dict):
            return default
        inner = outer.get(inner_key)
        if not isinstance(inner, dict):
            return default
        key   = self._sector_key(sector)
        value = inner.get(key)
        if value is None:
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def raw_section(self, section: str) -> Dict[str, Any]:
        return self._data.get(section) or {}

    @staticmethod
    def _sector_key(sector: Optional[Sectors]) -> str:
        return sector.value if sector is not None else ""

    def _lookup(self, section: str, sector: Optional[Sectors]) -> Any:
        section_data = self._data.get(section)
        if not isinstance(section_data, dict):
            return None
        return section_data.get(self._sector_key(sector))


@lru_cache(maxsize=None)
def load_valuation_config(name: str) -> ValuationConfig:
    path = _CONFIG_ROOT / "valuations" / f"{name}.yaml"
    return _load(path)


@lru_cache(maxsize=None)
def load_validator_config(name: str) -> ValuationConfig:
    path = _CONFIG_ROOT / "validators" / f"{name}.yaml"
    return _load(path)


def _load(path: Path) -> ValuationConfig:
    if not path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {path}. "
            "Ensure the file exists under src/config/."
        )
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    logger.debug("Loaded config from %s (%d top-level keys).", path, len(data))
    return ValuationConfig(data, path)
