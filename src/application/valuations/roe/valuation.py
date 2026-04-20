import logging
from typing import Dict, List, Optional

from calculations import safe_div
from domain.metrics.stock import StockMetrics
from domain.valuation.models.roe import (
    ROEParameters,
    ROEValuationInput,
    ROEValuationReport,
    ROEValuationResult,
)

from ..utils import evaluate_price, generate_growth_scenarios
from .defaults import get_params

logger = logging.getLogger(__name__)


def roe_valuation(input: ROEValuationInput) -> ROEValuationResult:
    equity_per_share_progression: List[float] = []
    dividend_progression: List[float] = []
    npv_dividend_progression: List[float] = []
    sm = input.stock_metrics
    pm = input.params

    equity_per_share = safe_div(
        sm.balance_sheet.total_equity,
        sm.market_data.shares_outstanding,
    )
    if equity_per_share is None:
        raise ValueError(
            "shares_outstanding and total_equity must be positive for ROE valuation. "
            "Run ROEChecker.evaluate() before calling execute_roe_scenarios()."
        )
    dividend = input.dividend_rate_per_share

    for year in range(1, pm.projection_years + 1):
        growth_rate = input.growth_rates[year - 1]
        equity_per_share = equity_per_share * (1 + growth_rate)

        dividend *= (1 + growth_rate)
        npv_dividend = dividend / ((1 + pm.discount_rate) ** (year - 1))
        equity_per_share_progression.append(equity_per_share)
        dividend_progression.append(dividend)
        npv_dividend_progression.append(npv_dividend)

    ratios = sm.ratios
    if ratios is None:
        raise ValueError("ratios must be available for ROE valuation.")

    return_on_equity = ratios.return_on_equity
    if return_on_equity == 0.0:
        raise ValueError("return_on_equity must be non-zero for ROE valuation.")

    year_n_income      = return_on_equity * equity_per_share_progression[-1]
    required_value     = year_n_income / pm.discount_rate
    npv_required_value = required_value / ((1 + pm.discount_rate) ** pm.projection_years)
    npv_dividends      = sum(npv_dividend_progression)
    intrinsic_value    = npv_required_value + npv_dividends

    valuation_status = evaluate_price(
        current_price=sm.market_data.current_price,
        intrinsic_value=intrinsic_value,
    )

    return ROEValuationResult(
        growth_rates=input.growth_rates,
        valuation_status=valuation_status,
        shareholders_equity_progression=equity_per_share_progression,
        dividend_progression=dividend_progression,
        npv_dividend_progression=npv_dividend_progression,
        year_n_income=year_n_income,
        required_value=required_value,
        npv_required_value=npv_required_value,
        npv_dividends=npv_dividends,
        intrinsic_value=intrinsic_value,
    )


def execute_roe_scenarios(
    stock_metrics: StockMetrics,
    params: Optional[ROEParameters] = None,
) -> ROEValuationReport:
    """
    Build Bear / Base / Bull ROE valuation scenarios.
    """
    if params is None:
        params = get_params(stock_metrics)

    # dividends_paid_ttm is float = 0.0 — no None guard needed.
    # abs() normalises the sign (yfinance sometimes returns negative outflows).
    raw_dividends = abs(stock_metrics.cash_flow.dividends_paid_ttm)

    dividend_rate_per_share = safe_div(
        raw_dividends,
        stock_metrics.market_data.shares_outstanding,
    )

    if dividend_rate_per_share is None:
        shares = stock_metrics.market_data.shares_outstanding
        logger.error(
            "ROE valuation aborted for %s: shares_outstanding is %s. "
            "Call ROEChecker.evaluate() first to surface this as a validation error.",
            stock_metrics.profile.ticker,
            shares,
        )
        raise ValueError(
            f"Cannot compute dividend_rate_per_share: shares_outstanding is "
            f"{shares!r} (must be a positive number). "
            "Run ROEChecker.evaluate() before execute_roe_scenarios()."
        )

    growth_scenarios = generate_growth_scenarios(
        stock_metrics, params.projection_years, params.margin_of_safety,
    )

    scenarios: Dict[str, ROEValuationResult] = {}
    for name, growth_rate in growth_scenarios.items():
        roe_input = ROEValuationInput(
            stock_metrics=stock_metrics,
            dividend_rate_per_share=dividend_rate_per_share,
            growth_rates=growth_rate,
            params=params,
        )
        scenarios[name] = roe_valuation(roe_input)

    return ROEValuationReport(scenarios=scenarios, params=params)
