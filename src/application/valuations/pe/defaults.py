from domain.core.enums import Sectors
from domain.metrics.stock import StockMetrics
from domain.valuation.models.pe import PEParameters

PE_MARGIN_OF_SAFETY = {
    Sectors.BASIC_MATERIALS: 0.35,
    Sectors.COMMUNICATION_SERVICES: 0.25,
    Sectors.CONSUMER_CYCLICAL: 0.30,
    Sectors.CONSUMER_DEFENSIVE: 0.20,
    Sectors.ENERGY: 0.35,
    Sectors.FINANCIAL_SERVICES: 0.25,
    Sectors.HEALTHCARE: 0.20,
    Sectors.INDUSTRIALS: 0.25,
    Sectors.REAL_ESTATE: 0.30,
    Sectors.TECHNOLOGY: 0.25,
    Sectors.UTILITIES: 0.20,
}


PE_DISCOUNT_RATE = {
    Sectors.BASIC_MATERIALS: 0.095,
    Sectors.COMMUNICATION_SERVICES: 0.090,
    Sectors.CONSUMER_CYCLICAL: 0.100,
    Sectors.CONSUMER_DEFENSIVE: 0.085,
    Sectors.ENERGY: 0.105,
    Sectors.FINANCIAL_SERVICES: 0.090, 
    Sectors.HEALTHCARE: 0.088,
    Sectors.INDUSTRIALS: 0.095,
    Sectors.REAL_ESTATE: 0.090,
    Sectors.TECHNOLOGY: 0.100,
    Sectors.UTILITIES: 0.080,
}


def get_params(
    stock_metrics: StockMetrics,
    projection_years: int = 10
) -> PEParameters:
    sector: Sectors = stock_metrics.profile.sector

    margin_of_safety = PE_MARGIN_OF_SAFETY.get(sector, 0.25)
    discount_rate = PE_DISCOUNT_RATE.get(sector, 0.09)

    return PEParameters(
        margin_of_sefty=margin_of_safety,
        discount_rate=discount_rate,
        projection_years=projection_years
    )
