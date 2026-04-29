from typing import Dict, Optional

from domain.metrics.stock import StockMetrics
from domain.valuation.models.ev_ebitda import (
    EVEBITDAParameters,
    EVEBITDAValuationInput,
    EVEBITDAValuationReport,
    EVEBITDAValuationResult,
)

from ..utils import evaluate_price
from .defaults import get_multiple, get_params


def ev_ebitda_valuation(input: EVEBITDAValuationInput) -> EVEBITDAValuationResult:
    """
    Single EV/EBITDA scenario.

    Formula:
        Intrinsic EV  = sector_multiple × EBITDA_TTM
        Equity Value  = Intrinsic EV − Total Debt + Cash
        IV / Share    = Equity Value / Shares Outstanding
    """
    sm = input.stock_metrics
    multiple = input.ebitda_multiple

    intrinsic_ev  = multiple * sm.financials.ebitda_ttm
    equity_value  = intrinsic_ev - sm.balance_sheet.total_debt + sm.balance_sheet.cash_and_equivalents
    shares        = sm.market_data.shares_outstanding

    if shares <= 0:
        raise ValueError("shares_outstanding must be positive for EV/EBITDA per-share calc.")

    iv_per_share = equity_value / shares

    status = evaluate_price(
        current_price=sm.market_data.current_price,
        intrinsic_value=iv_per_share,
    )

    return EVEBITDAValuationResult(
        scenario=input.scenario,
        ebitda_multiple_used=multiple,
        intrinsic_ev=intrinsic_ev,
        equity_value=equity_value,
        intrinsic_value_per_share=iv_per_share,
        valuation_status=status,
        total_debt=sm.balance_sheet.total_debt,
        cash_and_equivalents=sm.balance_sheet.cash_and_equivalents,
    )


def execute_ev_ebitda_scenarios(
    stock_metrics: StockMetrics,
    params: Optional[EVEBITDAParameters] = None,
) -> EVEBITDAValuationReport:
    if params is None:
        params = get_params(stock_metrics)

    scenarios: Dict[str, EVEBITDAValuationResult] = {}
    for scenario_name in ("Bear", "Base", "Bull"):
        multiple = get_multiple(stock_metrics, scenario_name)
        if multiple is None:
            sector = stock_metrics.profile.sector
            sector_label = sector.value if sector is not None else "unknown"
            raise ValueError(
                f"No EV/EBITDA multiple configured for {scenario_name} scenario "
                f"and sector {sector_label!r}."
            )
        input_data = EVEBITDAValuationInput(
            stock_metrics=stock_metrics,
            ebitda_multiple=multiple,
            params=params,
            scenario=scenario_name,
        )
        scenarios[scenario_name] = ev_ebitda_valuation(input_data)

    return EVEBITDAValuationReport(
        scenarios=scenarios,
        params=params,
        ebitda_ttm=stock_metrics.financials.ebitda_ttm,
    )
