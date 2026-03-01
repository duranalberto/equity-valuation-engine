from typing import List, Dict, Optional
from domain.metrics.stock import StockMetrics
from domain.valuation.base import ValuationReport
from domain.valuation.models.pe import PEValuationResult, PEValuationInput, PEParameters
from .defaults import get_params
from ..utils import generate_growth_scenarios, evaluate_price


def pe_valuation(input: PEValuationInput) -> PEValuationResult:
    eps = input.stock_metrics.market_data.eps_ttm
    eps_progression = []

    for year in range(input.params.projection_years):
        eps *= (1 + input.growth_rates[year])
        eps_progression.append(eps)

    value_in_x_years = eps * input.stock_metrics.valuation.median_historical_pe
    present_value = (1 + input.params.discount_rate) ** input.params.projection_years
    present_value = value_in_x_years / present_value
    
    valuation_status = evaluate_price(
        current_price=input.stock_metrics.market_data.current_price,
        intrinsic_value=present_value
    )

    return PEValuationResult(
        growth_rates=input.growth_rates,
        eps_progression=eps_progression,
        value_in_x_years=value_in_x_years,
        present_value=present_value,
        valuation_status=valuation_status
    )


def execute_pe_scenarios(
    stock_metrics: StockMetrics,
    params: Optional[PEParameters] = None
) -> Dict[str, PEValuationResult]:
    if(params is None):
        params = get_params(stock_metrics)
        
    growth_scenarios = generate_growth_scenarios(
        stock_metrics,
        params.projection_years,
        params.margin_of_sefty
    )
    
    scenarios:Dict[str, PEValuationResult] = {}
    for name, growth_rate in growth_scenarios.items():
        pe_input = PEValuationInput(
            stock_metrics=stock_metrics,
            growth_rates=growth_rate,
            params=params
        )
        scenarios[name] = pe_valuation(pe_input)

    return ValuationReport(
        scenarios=scenarios,
        params=params
    )

