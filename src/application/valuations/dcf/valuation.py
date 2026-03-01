from typing import Dict, List, Optional
from domain.valuation.models.dcf import DCFParameters, DCFInputData, DCFValuationResult, DCFValuationReport
from domain.metrics.stock import StockMetrics

from calculations.dfc_formulas import (
    intrinsic_value_per_share, market_enterprise_value, market_implied_wacc,
    cost_of_equity_capm, compute_discounted_cash_flow, compute_wacc
)
from .defaults import get_params
from ..utils import generate_growth_scenarios, evaluate_price


def create_fcf_projections(
    initial_fcf: float,
    growth_rates: List[float]
) -> List[float]:
    fcf = initial_fcf
    projections: List[float] = []
    for g in growth_rates:
        fcf = fcf * (1 + g)
        projections.append(fcf)

    return projections


def dcf_valuation(input: DCFInputData) -> DCFValuationResult:
    sm = input.stock_metrics
    
    fcf_projections = create_fcf_projections(
        initial_fcf=sm.cash_flow.fcf_ttm,
        growth_rates=input.growth_rates
    )
    

    dcf_output = compute_discounted_cash_flow(
        fcf_projections,
        input.wacc.wacc,
        input.params.terminal_growth_rate
    )
    

    intrinsic_value = intrinsic_value_per_share(
        dcf_output.enterprise_value,
        sm.market_data.shares_outstanding
    )

    valuation_status = evaluate_price(
        current_price=sm.market_data.current_price,
        intrinsic_value=intrinsic_value
    )
    

    market_ev = market_enterprise_value(
        market_cap=sm.market_data.market_cap,
        total_debt=sm.balance_sheet.total_debt,
        cash_and_equivalents=sm.balance_sheet.cash_and_equivalents
    )
    

    implied_wacc = market_implied_wacc(
        target_enterprise_value=market_ev,
        terminal_growth_rate=input.params.terminal_growth_rate,
        fcf_projections=fcf_projections
    )

    return DCFValuationResult(
        growth_rates=input.growth_rates,
        fcf_projections=fcf_projections,
        dcf=dcf_output,
        intrinsic_value_per_share=intrinsic_value,
        implied_wacc=implied_wacc,
        valuation_status=valuation_status,
    )


def execute_dcf_scenarios(
    stock_metrics: StockMetrics,
    params: Optional[DCFParameters] = None
) ->  DCFValuationReport:
    if(params is None):
        params = get_params(stock_metrics)
    cost_of_equity = cost_of_equity_capm(
        risk_free_rate=params.risk_free_rate,
        beta=stock_metrics.market_data.beta,
        market_risk_premium=params.market_risk_premium
    )

    wacc = compute_wacc(
        market_cap=stock_metrics.market_data.market_cap,
        total_debt=stock_metrics.balance_sheet.total_debt,
        cost_of_equity=cost_of_equity,
        cost_of_debt=stock_metrics.valuation.cost_of_debt,
        tax_rate=stock_metrics.valuation.corporate_tax_rate
    )
    
    growth_scenarios = generate_growth_scenarios(
        stock_metrics,
        params.projection_years,
        params.margin_of_sefty
    )
    
    
    scenarios:Dict[str, DCFValuationResult] = {}
    for name, growth_rate in growth_scenarios.items():
        dcf_input = DCFInputData(
            stock_metrics=stock_metrics,
            growth_rates=growth_rate,
            wacc= wacc,
            params=params
        )
        scenarios[name] = dcf_valuation(dcf_input)
    
    return DCFValuationReport(
        scenarios=scenarios,
        params=params,
        wacc=wacc
    )

