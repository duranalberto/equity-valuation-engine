from domain.core.enums import Sectors
from domain.metrics.stock import StockMetrics
from domain.valuation.models.roe import ROEParameters

ROE_MARGIN_OF_SAFETY = {
    Sectors.BASIC_MATERIALS: 0.35,
    Sectors.COMMUNICATION_SERVICES: 0.25,
    Sectors.CONSUMER_CYCLICAL: 0.30,
    Sectors.CONSUMER_DEFENSIVE: 0.20,
    Sectors.ENERGY: 0.40,
    Sectors.FINANCIAL_SERVICES: 0.30,
    Sectors.HEALTHCARE: 0.20,
    Sectors.INDUSTRIALS: 0.25,
    Sectors.REAL_ESTATE: 0.35,
    Sectors.TECHNOLOGY: 0.30,
    Sectors.UTILITIES: 0.15,


ROE_DISCOUNT_RATE = {
    Sectors.BASIC_MATERIALS: 0.105,
    Sectors.COMMUNICATION_SERVICES: 0.095,
    Sectors.CONSUMER_CYCLICAL: 0.110,
    Sectors.CONSUMER_DEFENSIVE: 0.090,
    Sectors.ENERGY: 0.115,
    Sectors.FINANCIAL_SERVICES: 0.100,
    Sectors.HEALTHCARE: 0.095,
    Sectors.INDUSTRIALS: 0.100,
    Sectors.REAL_ESTATE: 0.095,
    Sectors.TECHNOLOGY: 0.110,
    Sectors.UTILITIES: 0.085,
}

def get_params(
    stock_metrics: StockMetrics,
    projection_years: int = 10
) -> ROEParameters:
    sector: Sectors = stock_metrics.profile.sector

    margin_of_safety = ROE_MARGIN_OF_SAFETY.get(sector, 0.25)
    discount_rate = ROE_DISCOUNT_RATE.get(sector, 0.09)

    return ROEParameters(
        margin_of_safty=margin_of_safety,
        discount_rate=discount_rate,
        projection_years=projection_years
    )
