from typing import Optional

from config.config_loader import load_valuation_config
from domain.core.enums import Sectors
from domain.metrics.stock import StockMetrics
from domain.valuation.models.ev_ebitda import EVEBITDAParameters

_cfg = load_valuation_config("multiples")


def get_params(stock_metrics: StockMetrics, projection_years: int = 10) -> EVEBITDAParameters:
    return EVEBITDAParameters(
        margin_of_safety=0.0,   # multiples already span Bear/Base/Bull — no extra MOS layer
        projection_years=projection_years,
    )


def get_multiple(stock_metrics: StockMetrics, scenario: str) -> Optional[float]:
    """Return the sector EV/EBITDA multiple for Bear / Base / Bull scenario."""
    sector: Sectors = stock_metrics.profile.sector
    if sector is None:
        return None
    key = scenario.lower()   # "bear" | "base" | "bull"
    section = _cfg.raw_section("ev_ebitda")
    values = section.get(key) if isinstance(section, dict) else None
    if not isinstance(values, dict):
        return None
    value = values.get(sector.value)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
