from config.config_loader import load_valuation_config
from domain.metrics.stock import StockMetrics
from domain.valuation.models.nav import NAVParameters

_cfg = load_valuation_config("nav")


def get_params(stock_metrics: StockMetrics, projection_years: int = 10) -> NAVParameters:
    return NAVParameters(margin_of_safety=0.0, projection_years=projection_years)


def get_haircut(stock_metrics: StockMetrics, scenario: str) -> float:
    sector = stock_metrics.profile.sector
    key = scenario.lower()
    return _cfg.get_nested_float("asset_haircut", key, sector, default=0.80)


def get_intangible_cap(stock_metrics: StockMetrics) -> float:
    sector = stock_metrics.profile.sector
    return _cfg.get_float("intangible_cap", sector, default=0.35)
