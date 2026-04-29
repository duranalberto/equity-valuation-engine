from config.config_loader import load_valuation_config
from domain.core.enums import Sectors
from domain.metrics.stock import StockMetrics
from domain.valuation.models.ddm import DDMParameters

_cfg = load_valuation_config("dcf")   # reuse dcf.yaml risk_free_rate / market_risk_premium


def get_params(stock_metrics: StockMetrics, projection_years: int = 10) -> DDMParameters:
    sector: Sectors = stock_metrics.profile.sector
    return DDMParameters(
        margin_of_safety=0.20,
        projection_years=projection_years,
        risk_free_rate=_cfg.get_float("risk_free_rate", sector, default=0.04),
        market_risk_premium=_cfg.get_float("market_risk_premium", sector, default=0.055),
        terminal_growth_rate=_cfg.get_float("terminal_growth_rate", sector, default=0.03),
    )
