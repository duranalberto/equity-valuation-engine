from config.config_loader import load_valuation_config
from domain.core.enums import Sectors
from domain.metrics.stock import StockMetrics
from domain.valuation.models.dcf import DCFParameters

_cfg = load_valuation_config("dcf")


def get_params(
    stock_metrics: StockMetrics,
    projection_years: int = 10,
) -> DCFParameters:
    sector: Sectors = stock_metrics.profile.sector

    return DCFParameters(
        margin_of_safety=_cfg.get_float("margin_of_safety",    sector, default=0.25),
        risk_free_rate=_cfg.get_float("risk_free_rate",         sector, default=0.04),
        market_risk_premium=_cfg.get_float("market_risk_premium", sector, default=0.055),
        terminal_growth_rate=_cfg.get_float("terminal_growth_rate", sector, default=0.02),
        projection_years=projection_years,
    )