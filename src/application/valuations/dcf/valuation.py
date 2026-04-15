from typing import Dict, List, Optional

from calculations.dfc_formulas import (
    compute_discounted_cash_flow,
    compute_wacc,
    cost_of_equity_capm,
    intrinsic_value_per_share,
    market_enterprise_value,
    market_implied_wacc,
)
from domain.metrics.stock import StockMetrics
from domain.valuation.models.dcf import (
    DCFInputData,
    DCFParameters,
    DCFSensitivityReport,
    DCFValuationReport,
    DCFValuationResult,
)

from ..utils import evaluate_price, generate_growth_scenarios
from .defaults import get_params


def create_fcf_projections(
    initial_fcf: float,
    growth_rates: List[float],
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
        growth_rates=input.growth_rates,
    )

    dcf_output = compute_discounted_cash_flow(
        fcf_projections,
        input.wacc.wacc,
        input.params.terminal_growth_rate,
    )

    equity_value = dcf_output.enterprise_value
    if sm.balance_sheet.total_debt is not None:
        equity_value -= sm.balance_sheet.total_debt
    if sm.balance_sheet.cash_and_equivalents is not None:
        equity_value += sm.balance_sheet.cash_and_equivalents

    intrinsic_value = intrinsic_value_per_share(
        equity_value,
        sm.market_data.shares_outstanding,
    )

    valuation_status = evaluate_price(
        current_price=sm.market_data.current_price,
        intrinsic_value=intrinsic_value,
    )

    market_ev = market_enterprise_value(
        market_cap=sm.market_data.market_cap,
        total_debt=sm.balance_sheet.total_debt,
        cash_and_equivalents=sm.balance_sheet.cash_and_equivalents,
    )

    implied_wacc = market_implied_wacc(
        target_enterprise_value=market_ev,
        terminal_growth_rate=input.params.terminal_growth_rate,
        fcf_projections=fcf_projections,
    )

    return DCFValuationResult(
        growth_rates=input.growth_rates,
        valuation_status=valuation_status,
        fcf_projections=fcf_projections,
        dcf=dcf_output,
        intrinsic_value_per_share=intrinsic_value,
        implied_wacc=implied_wacc,
    )


def _compute_sensitivity(
    stock_metrics: StockMetrics,
    base_fcf_projections: List[float],
    wacc_values: List[float],
    terminal_growth_values: List[float],
) -> List[List[float | None]]:
    """
    Build a 2-D intrinsic-value-per-share matrix.

    Rows  → wacc_values (ascending)
    Cols  → terminal_growth_values (ascending)

    A cell is ``None`` when WACC ≤ terminal_growth_rate (Gordon Growth Model
    is undefined) or when the resulting equity value would be nonsensical.
    """
    matrix: List[List[float | None]] = []
    total_debt = stock_metrics.balance_sheet.total_debt or 0.0
    cash = stock_metrics.balance_sheet.cash_and_equivalents or 0.0
    shares = stock_metrics.market_data.shares_outstanding

    for wacc_rate in wacc_values:
        row: List[float | None] = []
        for tgr in terminal_growth_values:
            if wacc_rate <= tgr:
                row.append(None)
                continue
            try:
                dcf_out = compute_discounted_cash_flow(
                    base_fcf_projections, wacc_rate, tgr
                )
                equity_value = dcf_out.enterprise_value - total_debt + cash
                iv = intrinsic_value_per_share(equity_value, shares)
                row.append(round(iv, 4))
            except Exception:
                row.append(None)
        matrix.append(row)
    return matrix


def build_sensitivity_report(
    stock_metrics: StockMetrics,
    base_fcf_projections: List[float],
    base_wacc: float,
    base_terminal_growth: float,
    scenario_name: str = "Base",
    wacc_steps: int = 5,
    tgr_steps: int = 5,
    wacc_spread: float = 0.02,
    tgr_spread: float = 0.01,
) -> DCFSensitivityReport:
    """
    Construct a WACC × terminal-growth-rate sensitivity report.

    The base values are always included as the central entry.  The axes are
    built symmetrically around the base with ``wacc_steps`` and ``tgr_steps``
    total points (including the base).

    Parameters
    ----------
    wacc_spread  : total range around the base WACC (e.g. 0.02 → ±1 %).
    tgr_spread   : total range around the base terminal growth rate (e.g. 0.01 → ±0.5 %).
    wacc_steps   : number of WACC axis points (odd numbers produce a centred grid).
    tgr_steps    : number of terminal growth rate axis points.
    """
    def _axis(centre: float, spread: float, steps: int) -> List[float]:
        if steps <= 1:
            return [centre]
        delta = spread / (steps - 1)
        raw = [centre - spread / 2 + i * delta for i in range(steps)]
        if centre not in raw:
            raw.append(centre)
            raw.sort()
        return [round(v, 6) for v in raw]

    wacc_values = _axis(base_wacc, wacc_spread, wacc_steps)
    tgr_values  = _axis(base_terminal_growth, tgr_spread, tgr_steps)

    matrix = _compute_sensitivity(
        stock_metrics, base_fcf_projections, wacc_values, tgr_values
    )

    return DCFSensitivityReport(
        wacc_values=wacc_values,
        terminal_growth_values=tgr_values,
        intrinsic_values=matrix,
        base_wacc=base_wacc,
        base_terminal_growth=base_terminal_growth,
        scenario_name=scenario_name,
    )


def execute_dcf_scenarios(
    stock_metrics: StockMetrics,
    params: Optional[DCFParameters] = None,
) -> DCFValuationReport:
    if params is None:
        params = get_params(stock_metrics)

    cost_of_equity = cost_of_equity_capm(
        risk_free_rate=params.risk_free_rate,
        beta=stock_metrics.market_data.beta,
        market_risk_premium=params.market_risk_premium,
    )

    wacc = compute_wacc(
        market_cap=stock_metrics.market_data.market_cap,
        total_debt=stock_metrics.balance_sheet.total_debt,
        cost_of_equity=cost_of_equity,
        cost_of_debt=stock_metrics.valuation.cost_of_debt,
        tax_rate=stock_metrics.valuation.corporate_tax_rate,
    )

    growth_scenarios = generate_growth_scenarios(
        stock_metrics,
        params.projection_years,
        params.margin_of_safety,
    )

    scenarios: Dict[str, DCFValuationResult] = {}
    for name, growth_rate in growth_scenarios.items():
        dcf_input = DCFInputData(
            stock_metrics=stock_metrics,
            growth_rates=growth_rate,
            wacc=wacc,
            params=params,
        )
        scenarios[name] = dcf_valuation(dcf_input)

    base_projections = scenarios["Base"].fcf_projections if "Base" in scenarios else (
        next(iter(scenarios.values())).fcf_projections if scenarios else []
    )
    sensitivity = build_sensitivity_report(
        stock_metrics=stock_metrics,
        base_fcf_projections=base_projections,
        base_wacc=wacc.wacc,
        base_terminal_growth=params.terminal_growth_rate,
        scenario_name="Base",
    )

    return DCFValuationReport(
        scenarios=scenarios,
        params=params,
        wacc=wacc,
        sensitivity=sensitivity,
    )
