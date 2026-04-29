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
    """
    Compute a single ROE scenario.

    BUG-C fix: apply roe_cap from params before computing terminal income.
    When the live ROE exceeds the sector cap the capped value is used and
    ``roe_was_capped=True`` is set on the result so presenters / downstream
    consumers can annotate accordingly.
    """
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
        npv_dividend = dividend / ((1 + pm.discount_rate) ** year)
        equity_per_share_progression.append(equity_per_share)
        dividend_progression.append(dividend)
        npv_dividend_progression.append(npv_dividend)

    ratios = sm.ratios
    if ratios is None:
        raise ValueError("ratios must be available for ROE valuation.")

    raw_roe = ratios.return_on_equity
    if raw_roe == 0.0:
        raise ValueError("return_on_equity must be non-zero for ROE valuation.")

    # ── BUG-C fix: cap leverage-inflated ROE ──────────────────────────────────
    roe_was_capped = False
    effective_roe = raw_roe
    if pm.roe_cap is not None and raw_roe > pm.roe_cap:
        logger.warning(
            "[%s] ROE %.2f%% exceeds sector cap %.2f%%.  "
            "Terminal income will use capped ROE to prevent leverage-inflation compounding.",
            sm.profile.ticker,
            raw_roe * 100,
            pm.roe_cap * 100,
        )
        effective_roe = pm.roe_cap
        roe_was_capped = True
    # ─────────────────────────────────────────────────────────────────────────

    year_n_income      = effective_roe * equity_per_share_progression[-1]
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
        roe_was_capped=roe_was_capped,
        roe_applied=effective_roe,
        # buyback_substituted is set by execute_roe_scenarios() below
        buyback_substituted=input.buyback_substituted,
    )


def execute_roe_scenarios(
    stock_metrics: StockMetrics,
    params: Optional[ROEParameters] = None,
) -> ROEValuationReport:
    """
    Build Bear / Base / Bull ROE valuation scenarios.

    BUG-B fix: when dividends_paid_ttm is zero but share buybacks are
    positive, substitute buyback yield as the per-share distribution
    component.  This aligns the valuation with the promise already made
    by ROEChecker._check_buyback_dominance().

    The substitution flag is propagated into every ROEValuationResult so
    that presenters can annotate the output clearly.
    """
    if params is None:
        params = get_params(stock_metrics)

    raw_dividends = abs(stock_metrics.cash_flow.dividends_paid_ttm)
    raw_buybacks  = abs(stock_metrics.cash_flow.share_buybacks_ttm)
    shares        = stock_metrics.market_data.shares_outstanding

    # ── BUG-B fix: substitute buyback yield when dividends are zero ───────────
    buyback_substituted = False
    if raw_dividends == 0.0 and raw_buybacks > 0.0:
        distribution_pool = raw_buybacks
        buyback_substituted = True
        logger.info(
            "[%s] ROE model: dividends_paid_ttm is zero.  "
            "Using share_buybacks_ttm (%.2fB) as distribution component "
            "(buyback yield = %.2f%%).",
            stock_metrics.profile.ticker,
            raw_buybacks / 1e9,
            (raw_buybacks / stock_metrics.market_data.market_cap) * 100
            if stock_metrics.market_data.market_cap > 0 else 0.0,
        )
    else:
        distribution_pool = raw_dividends
    # ─────────────────────────────────────────────────────────────────────────

    dividend_rate_per_share = safe_div(distribution_pool, shares)

    if dividend_rate_per_share is None:
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
            buyback_substituted=buyback_substituted,
        )
        scenarios[name] = roe_valuation(roe_input)

    return ROEValuationReport(scenarios=scenarios, params=params)