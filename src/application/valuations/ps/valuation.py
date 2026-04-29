from typing import Dict, Optional

from domain.metrics.stock import StockMetrics
from domain.valuation.models.ps import PSParameters, PSValuationReport, PSValuationResult

from ..utils import evaluate_price
from .defaults import get_multiple, get_params


def execute_ps_scenarios(
    stock_metrics: StockMetrics,
    params: Optional[PSParameters] = None,
) -> PSValuationReport:
    """
    P/S scenario execution.

    Formula:
        Intrinsic Market Cap = sector_ps_multiple × revenue_ttm
        IV / Share           = Intrinsic Market Cap / shares_outstanding
    """
    if params is None:
        params = get_params(stock_metrics)

    revenue_ttm    = stock_metrics.financials.revenue_ttm
    shares         = stock_metrics.market_data.shares_outstanding
    current_price  = stock_metrics.market_data.current_price
    market_cap     = stock_metrics.market_data.market_cap

    if shares <= 0:
        raise ValueError("shares_outstanding must be positive for P/S per-share calc.")

    implied_rev_multiple = (market_cap / revenue_ttm) if revenue_ttm > 0 else 0.0

    scenarios: Dict[str, PSValuationResult] = {}
    for scenario_name in ("Bear", "Base", "Bull"):
        multiple             = get_multiple(stock_metrics, scenario_name)
        if multiple is None:
            sector = stock_metrics.profile.sector
            sector_label = sector.value if sector is not None else "unknown"
            raise ValueError(
                f"No P/S multiple configured for {scenario_name} scenario "
                f"and sector {sector_label!r}."
            )
        intrinsic_market_cap = multiple * revenue_ttm
        iv_per_share         = intrinsic_market_cap / shares
        status               = evaluate_price(current_price=current_price, intrinsic_value=iv_per_share)

        scenarios[scenario_name] = PSValuationResult(
            scenario=scenario_name,
            ps_multiple_used=multiple,
            intrinsic_market_cap=intrinsic_market_cap,
            intrinsic_value_per_share=iv_per_share,
            valuation_status=status,
            implied_revenue_multiple=implied_rev_multiple,
            revenue_ttm=revenue_ttm,
        )

    return PSValuationReport(scenarios=scenarios, params=params, revenue_ttm=revenue_ttm)
