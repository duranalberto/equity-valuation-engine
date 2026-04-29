from config.config_loader import load_valuation_config
from domain.metrics.stock import StockMetrics
from domain.valuation.models.reverse_dcf import ReverseDCFParameters

_cfg = load_valuation_config("dcf")


def get_params(stock_metrics: StockMetrics, projection_years: int = 10) -> ReverseDCFParameters:
    sector = stock_metrics.profile.sector
    return ReverseDCFParameters(
        margin_of_safety=0.0,       # not meaningful for a back-solver
        projection_years=projection_years,
        risk_free_rate=_cfg.get_float("risk_free_rate", sector, default=0.04),
        market_risk_premium=_cfg.get_float("market_risk_premium", sector, default=0.055),
        terminal_growth_rate=_cfg.get_float("terminal_growth_rate", sector, default=0.02),
    )
