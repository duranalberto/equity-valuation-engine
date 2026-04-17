from config.config_loader import load_valuation_config
from domain.core.enums import Sectors
from domain.metrics.stock import StockMetrics
from domain.valuation.models.roe import ROEParameters

_cfg = load_valuation_config("roe")


def get_params(stock_metrics: StockMetrics, projection_years: int = 10) -> ROEParameters:
    sector: Sectors = stock_metrics.profile.sector

    return ROEParameters(
        margin_of_safety=_cfg.get_float("margin_of_safety", sector, default=0.25),
        discount_rate=_cfg.get_float("discount_rate",       sector, default=0.09),
        projection_years=projection_years,
    )