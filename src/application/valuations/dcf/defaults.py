from domain.core.enums import Sectors
from domain.metrics.stock import StockMetrics
from domain.valuation.models.dcf import DCFParameters

DCF_MARGIN_OF_SAFETY = {
    Sectors.BASIC_MATERIALS: 0.30,
    Sectors.COMMUNICATION_SERVICES: 0.25,
    Sectors.CONSUMER_CYCLICAL: 0.30,
    Sectors.CONSUMER_DEFENSIVE: 0.20,
    Sectors.ENERGY: 0.35,
    Sectors.FINANCIAL_SERVICES: 0.25,
    Sectors.HEALTHCARE: 0.20,
    Sectors.INDUSTRIALS: 0.25,
    Sectors.REAL_ESTATE: 0.30,
    Sectors.TECHNOLOGY: 0.30,
    Sectors.UTILITIES: 0.20,
}

DCF_RISK_FREE_RATE = {
    Sectors.BASIC_MATERIALS: 0.040,
    Sectors.COMMUNICATION_SERVICES: 0.040,
    Sectors.CONSUMER_CYCLICAL: 0.040,
    Sectors.CONSUMER_DEFENSIVE: 0.038,
    Sectors.ENERGY: 0.042,
    Sectors.FINANCIAL_SERVICES: 0.040,
    Sectors.HEALTHCARE: 0.038,
    Sectors.INDUSTRIALS: 0.040,
    Sectors.REAL_ESTATE: 0.043,
    Sectors.TECHNOLOGY: 0.040,
    Sectors.UTILITIES: 0.038,
}

DCF_MARKET_RISK_PREMIUM = {
    Sectors.BASIC_MATERIALS: 0.055,
    Sectors.COMMUNICATION_SERVICES: 0.060,
    Sectors.CONSUMER_CYCLICAL: 0.060,
    Sectors.CONSUMER_DEFENSIVE: 0.050,
    Sectors.ENERGY: 0.060,
    Sectors.FINANCIAL_SERVICES: 0.055,
    Sectors.HEALTHCARE: 0.052,
    Sectors.INDUSTRIALS: 0.055,
    Sectors.REAL_ESTATE: 0.057,
    Sectors.TECHNOLOGY: 0.060,
    Sectors.UTILITIES: 0.050,
}

DCF_TERMINAL_GROWTH_RATE = {
    Sectors.BASIC_MATERIALS: 0.020,
    Sectors.COMMUNICATION_SERVICES: 0.020,
    Sectors.CONSUMER_CYCLICAL: 0.020,
    Sectors.CONSUMER_DEFENSIVE: 0.022,
    Sectors.ENERGY: 0.018,
    Sectors.FINANCIAL_SERVICES: 0.020,
    Sectors.HEALTHCARE: 0.022,
    Sectors.INDUSTRIALS: 0.020,
    Sectors.REAL_ESTATE: 0.018,
    Sectors.TECHNOLOGY: 0.022,
    Sectors.UTILITIES: 0.018,
}


def get_params(
    stock_metrics: StockMetrics,
    projection_years: int = 10,
) -> DCFParameters:
    sector: Sectors = stock_metrics.profile.sector

    return DCFParameters(
        margin_of_safety=DCF_MARGIN_OF_SAFETY.get(sector, 0.25),
        risk_free_rate=DCF_RISK_FREE_RATE.get(sector, 0.04),
        market_risk_premium=DCF_MARKET_RISK_PREMIUM.get(sector, 0.055),
        terminal_growth_rate=DCF_TERMINAL_GROWTH_RATE.get(sector, 0.02),
        projection_years=projection_years,
    )
