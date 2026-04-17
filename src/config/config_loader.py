"""
src/config/config_loader.py
===========================
Central loader for YAML-based configuration files.

Design
------
* ``ValuationConfig`` — thin wrapper around a loaded YAML dict that provides
  typed, sector-keyed look-ups with explicit fallback values.
* ``load_valuation_config(name)`` — cached factory; returns the same
  ``ValuationConfig`` instance for the same file on repeated calls.
* ``load_validator_config(name)`` — same pattern for validator threshold files.

File layout (relative to this module's parent directory ``src/``)::

    config/
        valuations/
            dcf.yaml
            pe.yaml
            roe.yaml
            scenarios.yaml
        validators/
            dcf.yaml

Usage example::

    from config.config_loader import load_valuation_config
    cfg = load_valuation_config("dcf")
    mos = cfg.get_float("margin_of_safety", sector, default=0.25)
"""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from domain.core.enums import Sectors

logger = logging.getLogger(__name__)

# Resolved once at import time — robust regardless of the working directory.
_CONFIG_ROOT = Path(__file__).parent


class ValuationConfig:
    """
    Thin, read-only wrapper around a YAML config dict.

    All look-ups are sector-keyed.  The ``Sectors`` enum value (e.g.
    ``Sectors.TECHNOLOGY``) is converted to its string representation
    (``"technology"``) for key matching — consistent with the enum definition
    and the YAML key naming convention.
    """

    def __init__(self, data: Dict[str, Any], source: Path) -> None:
        self._data   = data
        self._source = source

    # ------------------------------------------------------------------
    # Public look-up helpers
    # ------------------------------------------------------------------

    def get_float(
        self,
        section: str,
        sector: Optional[Sectors],
        default: float,
    ) -> float:
        """Return a float config value for *section* / *sector*, or *default*."""
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
        """Return an integer config value for *section* / *sector*, or *default*."""
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
        """
        Two-level look-up: ``data[outer_key][inner_key][sector_key]``.

        Used for the scenarios config where the top-level key is the section
        name (e.g. ``"scenario_multipliers"``) and the second key is the
        scenario name (e.g. ``"Bear"``).
        """
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
        """Return the raw dict for a top-level *section* key (empty dict if absent)."""
        return self._data.get(section) or {}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _sector_key(sector: Optional[Sectors]) -> str:
        """Convert a ``Sectors`` enum member to its YAML key string."""
        return sector.value if sector is not None else ""

    def _lookup(self, section: str, sector: Optional[Sectors]) -> Any:
        section_data = self._data.get(section)
        if not isinstance(section_data, dict):
            return None
        return section_data.get(self._sector_key(sector))


# ---------------------------------------------------------------------------
# Cached factories
# ---------------------------------------------------------------------------

@lru_cache(maxsize=None)
def load_valuation_config(name: str) -> ValuationConfig:
    """
    Load and cache ``config/valuations/<name>.yaml``.

    Parameters
    ----------
    name : str
        File stem, e.g. ``"dcf"``, ``"pe"``, ``"roe"``, ``"scenarios"``.

    Raises
    ------
    FileNotFoundError
        When the YAML file does not exist.
    yaml.YAMLError
        When the file contains invalid YAML.
    """
    path = _CONFIG_ROOT / "valuations" / f"{name}.yaml"
    return _load(path)


@lru_cache(maxsize=None)
def load_validator_config(name: str) -> ValuationConfig:
    """
    Load and cache ``config/validators/<name>.yaml``.

    Parameters
    ----------
    name : str
        File stem, e.g. ``"dcf"``.
    """
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