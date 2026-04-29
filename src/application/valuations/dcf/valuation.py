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

    fcf_seed = sm.cash_flow.fcf_ttm
    fcf_seed_source = "raw"

    if sm.valuation.capex_spike_detected and sm.valuation.normalized_fcf is not None:
        fcf_seed = sm.valuation.normalized_fcf
        fcf_seed_source = "normalized"

    fcf_projections = create_fcf_projections(
        initial_fcf=fcf_seed,
        growth_rates=input.growth_rates,
    )

    # BUG-E fix: compute_discounted_cash_flow now returns (dcf_output, fcf_tv_seed)
    dcf_output, fcf_tv_seed = compute_discounted_cash_flow(
        fcf_projections,
        input.wacc.wacc,
        input.params.terminal_growth_rate,
    )

    equity_value = (
        dcf_output.enterprise_value
        - sm.balance_sheet.total_debt
        + sm.balance_sheet.cash_and_equivalents
    )

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
        fcf_seed_source=fcf_seed_source,
        dcf=dcf_output,
        intrinsic_value_per_share=intrinsic_value,
        implied_wacc=implied_wacc,
        fcf_tv_seed=fcf_tv_seed,  # BUG-E: surface the TV averaging seed
    )


def _compute_sensitivity(
    stock_metrics: StockMetrics,
    base_fcf_projections: List[float],
    wacc_values: List[float],
    terminal_growth_values: List[float],
) -> List[List[Optional[float]]]:
    matrix: List[List[Optional[float]]] = []
    total_debt = stock_metrics.balance_sheet.total_debt
    cash       = stock_metrics.balance_sheet.cash_and_equivalents
    shares     = stock_metrics.market_data.shares_outstanding

    for wacc_rate in wacc_values:
        row: List[Optional[float]] = []
        for tgr in terminal_growth_values:
            if wacc_rate <= tgr:
                row.append(None)
                continue
            try:
                dcf_out, _ = compute_discounted_cash_flow(base_fcf_projections, wacc_rate, tgr)
                equity_value = dcf_out.enterprise_value - total_debt + cash
                iv = intrinsic_value_per_share(equity_value, shares)
                row.append(round(iv, 4))
            except Exception:
                row.append(None)
        matrix.append(row)
    return matrix


def _derive_sensitivity_spreads(
    stock_metrics: StockMetrics,
    base_wacc: float,
    base_terminal_growth: float,
) -> tuple[float, float]:
    """
    DESIGN-C fix: derive WACC and TGR spreads dynamically from beta and sector.

    WACC spread: wacc_spread = max(0.02, min(0.08, beta * 0.025))
      - beta=0.8 → 0.02 (±1pp, stable company)
      - beta=1.5 → 0.0375 (±1.9pp, moderate)
      - beta=2.0 → 0.05 (±2.5pp, volatile)
      - beta=2.07 (AI/C3.ai) → capped at 0.08 (maximum range)

    TGR spread: loaded from dcf.yaml tgr_spread section (sector-specific).
    Falls back to ±1.0pp (0.02 total) if not configured.

    Previously both were hardcoded (wacc_spread=0.04, tgr_spread=0.02), which
    applied the same grid to all companies regardless of uncertainty profile.
    """
    beta = getattr(stock_metrics.market_data, "beta", 1.0) or 1.0
    wacc_spread = max(0.02, min(0.08, beta * 0.025))

    # TGR spread: sector-differentiated via config; fall back to ±1pp
    try:
        from config.config_loader import load_valuation_config
        cfg = load_valuation_config("dcf")
        sector = getattr(stock_metrics.profile, "sector", None)
        tgr_spread = cfg.get_float("tgr_spread", sector, default=0.02)
    except Exception:
        tgr_spread = 0.02

    return wacc_spread, tgr_spread


def build_sensitivity_report(
    stock_metrics: StockMetrics,
    base_fcf_projections: List[float],
    base_wacc: float,
    base_terminal_growth: float,
    scenario_name: str = "Base",
    wacc_steps: int = 7,
    tgr_steps: int = 5,
    # DESIGN-C: these are now computed dynamically; explicit overrides still accepted.
    wacc_spread: Optional[float] = None,
    tgr_spread: Optional[float] = None,
) -> DCFSensitivityReport:
    # DESIGN-C fix: derive spreads from beta/sector when not explicitly overridden.
    derived_wacc_spread, derived_tgr_spread = _derive_sensitivity_spreads(
        stock_metrics, base_wacc, base_terminal_growth
    )
    effective_wacc_spread = wacc_spread if wacc_spread is not None else derived_wacc_spread
    effective_tgr_spread  = tgr_spread  if tgr_spread  is not None else derived_tgr_spread

    def _axis(centre: float, spread: float, steps: int) -> List[float]:
        if steps <= 1:
            return [centre]
        delta = spread / (steps - 1)
        raw = [centre - spread / 2 + i * delta for i in range(steps)]
        if centre not in raw:
            raw.append(centre)
            raw.sort()
        return [round(v, 6) for v in raw]

    wacc_values = _axis(base_wacc, effective_wacc_spread, wacc_steps)
    tgr_values  = _axis(base_terminal_growth, effective_tgr_spread, tgr_steps)

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
        # DESIGN-C: expose the derived spreads for transparency
        derived_wacc_spread=derived_wacc_spread,
        derived_tgr_spread=derived_tgr_spread,
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