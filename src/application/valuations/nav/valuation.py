from typing import Dict, Optional

from domain.metrics.stock import StockMetrics
from domain.valuation.models.nav import NAVParameters, NAVValuationReport, NAVValuationResult

from ..utils import evaluate_price
from .defaults import get_haircut, get_intangible_cap, get_params


def execute_nav_scenarios(
    stock_metrics: StockMetrics,
    params: Optional[NAVParameters] = None,
) -> NAVValuationReport:
    """
    NAV scenario execution.

    Formula:
        Adjusted Assets = total_assets × asset_haircut
        NAV             = Adjusted Assets − total_liabilities
        NAV/Share       = NAV / shares_outstanding
    """
    if params is None:
        params = get_params(stock_metrics)

    bs     = stock_metrics.balance_sheet
    shares = stock_metrics.market_data.shares_outstanding
    price  = stock_metrics.market_data.current_price

    if shares <= 0:
        raise ValueError("shares_outstanding must be positive for NAV per-share calc.")

    goodwill_and_intangibles = getattr(bs, "goodwill_and_intangibles", 0.0) or 0.0
    intangible_cap = get_intangible_cap(stock_metrics)
    intangible_ratio = (
        goodwill_and_intangibles / bs.total_assets if bs.total_assets > 0 else 0.0
    )
    intangible_warn = intangible_ratio > intangible_cap

    scenarios: Dict[str, NAVValuationResult] = {}
    for scenario_name in ("Bear", "Base", "Bull"):
        haircut        = get_haircut(stock_metrics, scenario_name)
        adj_assets     = bs.total_assets * haircut
        nav            = adj_assets - bs.total_liabilities
        nav_per_share  = nav / shares
        p2nav          = (price / nav_per_share) if nav_per_share != 0 else 0.0
        status         = evaluate_price(current_price=price, intrinsic_value=nav_per_share)

        scenarios[scenario_name] = NAVValuationResult(
            scenario=scenario_name,
            asset_haircut_used=haircut,
            adjusted_assets=adj_assets,
            total_liabilities=bs.total_liabilities,
            nav=nav,
            nav_per_share=nav_per_share,
            price_to_nav=p2nav,
            intrinsic_value_per_share=nav_per_share,
            valuation_status=status,
            goodwill_and_intangibles=goodwill_and_intangibles,
            intangible_asset_ratio=intangible_ratio,
            intangible_warning=intangible_warn,
        )

    return NAVValuationReport(
        scenarios=scenarios,
        params=params,
        total_assets=bs.total_assets,
        total_liabilities=bs.total_liabilities,
        total_equity=bs.total_equity,
        goodwill_and_intangibles=goodwill_and_intangibles,
        intangible_asset_ratio=intangible_ratio,
        intangible_cap=intangible_cap,
    )
