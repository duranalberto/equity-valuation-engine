from typing import Dict, List, Optional

from domain.metrics.stock import StockMetrics
from domain.valuation.models.pe import (
    PEParameters,
    PEValuationInput,
    PEValuationReport,
    PEValuationResult,
)

from ..utils import evaluate_price, generate_growth_scenarios
from .defaults import get_params


def pe_valuation(input: PEValuationInput) -> PEValuationResult:
    sm = input.stock_metrics

    # median_historical_pe stays Optional[float] in the domain model.
    # PEChecker._check_valuation_inputs() is the firewall that blocks execution
    # when it is None.  The guard here is a defensive backstop — it should
    # never be reached in normal operation.
    median_pe = sm.valuation.median_historical_pe
    if median_pe is None:
        raise ValueError(
            "median_historical_pe is None — run PEChecker.evaluate() before "
            "calling execute_pe_scenarios() to catch this as a validation error."
        )

    eps = sm.market_data.eps_ttm
    eps_progression: List[float] = []

    for year in range(input.params.projection_years):
        eps *= (1 + input.growth_rates[year])
        eps_progression.append(eps)

    value_in_x_years = eps * median_pe
    present_value = value_in_x_years / (
        (1 + input.params.discount_rate) ** input.params.projection_years
    )

    valuation_status = evaluate_price(
        current_price=sm.market_data.current_price,
        intrinsic_value=present_value,
    )

    return PEValuationResult(
        growth_rates=input.growth_rates,
        valuation_status=valuation_status,
        eps_progression=eps_progression,
        value_in_x_years=value_in_x_years,
        present_value=present_value,
    )


def execute_pe_scenarios(
    stock_metrics: StockMetrics,
    params: Optional[PEParameters] = None,
) -> PEValuationReport:
    if params is None:
        params = get_params(stock_metrics)

    growth_scenarios = generate_growth_scenarios(
        stock_metrics, params.projection_years, params.margin_of_safety,
    )

    scenarios: Dict[str, PEValuationResult] = {}
    for name, growth_rate in growth_scenarios.items():
        pe_input = PEValuationInput(
            stock_metrics=stock_metrics,
            growth_rates=growth_rate,
            params=params,
        )
        scenarios[name] = pe_valuation(pe_input)

    return PEValuationReport(scenarios=scenarios, params=params)
