from typing import List, Dict, Optional
from domain.metrics.stock import StockMetrics
from domain.valuation.base import ValuationReport
from domain.valuation.models.roe import ROEValuationInput, ROEParameters, ROEValuationResult
from .defaults import get_params
from ..utils import generate_growth_scenarios, evaluate_price


def roe_valuation(input: ROEValuationInput) -> ROEValuationResult:
    equity_per_share_progression: list[float] = []
    dividend_progression: list[float] = []
    npv_dividend_progression: list[float] = []
    sm = input.stock_metrics
    pm = input.params

    equity_per_share = sm.balance_sheet.total_equity
    dividend = input.dividend_rate_per_share

    for year in range(1, pm.projection_years + 1):
        growth_rate = input.growth_rates[year-1]
        if year == 1:
            equity_per_share = (equity_per_share * (1 + growth_rate)) / sm.market_data.shares_outstanding
        else:
            equity_per_share *= (1 + growth_rate)

        dividend *= (1 + growth_rate)
        npv_dividend = dividend / ((1 + pm.discount_rate) ** (year - 1))
        equity_per_share_progression.append(equity_per_share)
        dividend_progression.append(dividend)
        npv_dividend_progression.append(npv_dividend)

    year_n_income = sm.ratios.return_on_equity * equity_per_share_progression[-1]
    required_value = year_n_income / pm.discount_rate
    npv_required_value = required_value / ((1 + pm.discount_rate) ** pm.projection_years)

    npv_dividends = sum(npv_dividend_progression)

    intrinsic_value = npv_required_value + npv_dividends
    
    valuation_status = evaluate_price(
        current_price=input.stock_metrics.market_data.current_price,
        intrinsic_value=intrinsic_value
    )

    return ROEValuationResult(
        growth_rates=input.growth_rates,
        shareholders_equity_progression=equity_per_share_progression,
        dividend_progression=dividend_progression,
        npv_dividend_progression=npv_dividend_progression,
        year_n_income=year_n_income,
        required_value=required_value,
        npv_required_value=npv_required_value,
        npv_dividends=npv_dividends,
        intrisic_value=intrinsic_value,
        valuation_status=valuation_status
    )



def execute_roe_scenarios(
    stock_metrics: StockMetrics,
    params: Optional[ROEParameters] = None
) -> Dict[str, ROEValuationResult]:
    if(params is None):
        params = get_params(stock_metrics)
    
    raw_dividends = stock_metrics.cash_flow.dividends_paid_ttm
    
    if raw_dividends is None:
        raw_dividends = 0.0
    
    if raw_dividends < 0:
        raw_dividends = abs(raw_dividends)
    dividend_rate_per_share = raw_dividends / stock_metrics.market_data.shares_outstanding
    
    growth_scenarios = generate_growth_scenarios(
        stock_metrics,
        params.projection_years,
        params.margin_of_safty
    )

    scenarios: Dict[str, ROEValuationResult] = {}
    for name, growth_rate in growth_scenarios.items():

        roe_input = ROEValuationInput(
            stock_metrics=stock_metrics,
            dividend_rate_per_share=dividend_rate_per_share,
            growth_rates=growth_rate,
            params=params
        )

        result = roe_valuation(roe_input)
        scenarios[name] = result

    return ValuationReport(
        scenarios=scenarios,
        params=params
    )
