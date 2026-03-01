import random
from typing import Dict, List
from domain.core.enums import Sectors
from domain.metrics.stock import StockMetrics


SECTOR_GROWTH_MULTIPLIERS = {
    "Bear": {
        Sectors.BASIC_MATERIALS: 0.8,
        Sectors.COMMUNICATION_SERVICES: 0.8,
        Sectors.CONSUMER_CYCLICAL: 0.8,
        Sectors.CONSUMER_DEFENSIVE: 0.85,
        Sectors.ENERGY: 0.75,
        Sectors.FINANCIAL_SERVICES: 0.8,
        Sectors.HEALTHCARE: 0.85,
        Sectors.INDUSTRIALS: 0.8,
        Sectors.REAL_ESTATE: 0.8,
        Sectors.TECHNOLOGY: 0.8,
        Sectors.UTILITIES: 0.85,
    },
    "Base": {
        Sectors.BASIC_MATERIALS: 1.0,
        Sectors.COMMUNICATION_SERVICES: 1.0,
        Sectors.CONSUMER_CYCLICAL: 1.0,
        Sectors.CONSUMER_DEFENSIVE: 1.0,
        Sectors.ENERGY: 1.0,
        Sectors.FINANCIAL_SERVICES: 1.0,
        Sectors.HEALTHCARE: 1.0,
        Sectors.INDUSTRIALS: 1.0,
        Sectors.REAL_ESTATE: 1.0,
        Sectors.TECHNOLOGY: 1.0,
        Sectors.UTILITIES: 1.0,
    },
    "Bull": {
        Sectors.BASIC_MATERIALS: 1.2,
        Sectors.COMMUNICATION_SERVICES: 1.2,
        Sectors.CONSUMER_CYCLICAL: 1.2,
        Sectors.CONSUMER_DEFENSIVE: 1.15,
        Sectors.ENERGY: 1.2,
        Sectors.FINANCIAL_SERVICES: 1.2,
        Sectors.HEALTHCARE: 1.15,
        Sectors.INDUSTRIALS: 1.2,
        Sectors.REAL_ESTATE: 1.15,
        Sectors.TECHNOLOGY: 1.2,
        Sectors.UTILITIES: 1.1,
    }
}


SECTOR_VOLATILITY = {
    "Bear": {
        Sectors.BASIC_MATERIALS: 0.01,
        Sectors.COMMUNICATION_SERVICES: 0.01,
        Sectors.CONSUMER_CYCLICAL: 0.015,
        Sectors.CONSUMER_DEFENSIVE: 0.01,
        Sectors.ENERGY: 0.015,
        Sectors.FINANCIAL_SERVICES: 0.01,
        Sectors.HEALTHCARE: 0.01,
        Sectors.INDUSTRIALS: 0.01,
        Sectors.REAL_ESTATE: 0.01,
        Sectors.TECHNOLOGY: 0.02,
        Sectors.UTILITIES: 0.01,
    },
    "Base": {
        Sectors.BASIC_MATERIALS: 0.005,
        Sectors.COMMUNICATION_SERVICES: 0.005,
        Sectors.CONSUMER_CYCLICAL: 0.005,
        Sectors.CONSUMER_DEFENSIVE: 0.005,
        Sectors.ENERGY: 0.007,
        Sectors.FINANCIAL_SERVICES: 0.005,
        Sectors.HEALTHCARE: 0.005,
        Sectors.INDUSTRIALS: 0.005,
        Sectors.REAL_ESTATE: 0.005,
        Sectors.TECHNOLOGY: 0.01,
        Sectors.UTILITIES: 0.003,
    },
    "Bull": {
        Sectors.BASIC_MATERIALS: 0.02,
        Sectors.COMMUNICATION_SERVICES: 0.02,
        Sectors.CONSUMER_CYCLICAL: 0.02,
        Sectors.CONSUMER_DEFENSIVE: 0.015,
        Sectors.ENERGY: 0.02,
        Sectors.FINANCIAL_SERVICES: 0.02,
        Sectors.HEALTHCARE: 0.015,
        Sectors.INDUSTRIALS: 0.02,
        Sectors.REAL_ESTATE: 0.015,
        Sectors.TECHNOLOGY: 0.025,
        Sectors.UTILITIES: 0.01,
    }
}


#TODO implement sotck growth
def generate_growth_scenarios(
    stock_metrics: StockMetrics,
    projection_years: int,
    margin_of_safety: float = 0.25,
    random_seed: int = None
) -> Dict[str, List[float]]:

    if random_seed is not None:
        random.seed(random_seed)

    sector: Sectors = stock_metrics.profile.sector
    scenarios: Dict[str, List[float]] = {}
    
    BASE_GROWTH = 0.04
    for scenario_name in ["Bear", "Base", "Bull"]:
        multiplier = SECTOR_GROWTH_MULTIPLIERS[scenario_name][sector]
        volatility = SECTOR_VOLATILITY[scenario_name][sector]
        
        if scenario_name == "Bear":
            multiplier *= (1 - margin_of_safety)
        elif scenario_name == "Bull":
            multiplier *= (1 + margin_of_safety)
        
        growth_list = []
        for _ in range(projection_years):
            noise = random.uniform(-volatility, volatility)
            growth = BASE_GROWTH * multiplier + noise
            growth_list.append(growth)

        scenarios[scenario_name] = growth_list

    return scenarios


def evaluate_price(
    current_price: float,
    intrinsic_value: float,
    margin: float = 0.2
) -> str:
    lower = intrinsic_value * (1 - margin)
    upper = intrinsic_value * (1 + margin)
    if current_price < lower:
        return "undervalued"
    if current_price > upper:
        return "overvalued"
    return "reasonable"
