from typing import List, Optional
from domain.metrics.valuation import DiscountedCashFlow, WACC
from .common import safe_div, safe_sum


def market_enterprise_value(
    market_cap: Optional[float],
    total_debt: Optional[float],
    cash_and_equivalents: Optional[float],
) -> float:
    return safe_sum(market_cap, total_debt) - (cash_and_equivalents or 0.0)


def cost_of_equity_capm(
    risk_free_rate: float,
    beta: float,
    market_risk_premium: float,
) -> float:
    return risk_free_rate + beta * market_risk_premium


def intrinsic_value_per_share(
    equity_value: float,
    shares_outstanding: float,
) -> float:
    if shares_outstanding <= 0:
        raise ValueError(
            "Shares outstanding must be positive for per-share calculation."
        )
    return equity_value / shares_outstanding


def _discount_to_present(
    future_value: float,
    discount_rate: float,
    periods: int,
) -> float:
    if periods <= 0:
        raise ValueError("Periods must be greater than 0 for discounting.")
    result = safe_div(future_value, (1.0 + discount_rate) ** periods)
    return result if result is not None else 0.0


def _terminal_value_gordon(
    last_n_fcfs: List[float],
    discount_rate: float,
    terminal_growth_rate: float,
) -> float:
    if discount_rate <= terminal_growth_rate:
        raise ValueError(
            "Discount rate must be strictly greater than terminal growth rate."
        )
    if not last_n_fcfs:
        raise ValueError("At least one FCF is required.")
    n = min(3, len(last_n_fcfs))
    avg_fcf = sum(last_n_fcfs[-n:]) / float(n)
    fcf_next = avg_fcf * (1.0 + terminal_growth_rate)
    return fcf_next / (discount_rate - terminal_growth_rate)


def market_implied_wacc(
    target_enterprise_value: float,
    terminal_growth_rate: float,
    fcf_projections: List[float],
) -> float:
    if target_enterprise_value <= 0 or not fcf_projections:
        raise ValueError(
            "Valid positive enterprise value and FCF projections are required."
        )
    low = max(terminal_growth_rate + 1e-6, 1e-4)
    high = 1.0
    last_fcfs = fcf_projections[-3:]
    num_years = len(fcf_projections)

    for _ in range(100):
        mid = (low + high) / 2
        pv_fcfs = sum(
            _discount_to_present(fcf, mid, i + 1)
            for i, fcf in enumerate(fcf_projections)
        )
        try:
            tv = _terminal_value_gordon(last_fcfs, mid, terminal_growth_rate)
        except ValueError:
            value = float("inf")
        else:
            pv_tv = _discount_to_present(tv, mid, num_years)
            value = pv_fcfs + pv_tv

        if value > target_enterprise_value:
            low = mid
        else:
            high = mid

    return round((low + high) / 2, 6)


def _present_value_of_fcfs(
    fcf_projections: List[float],
    discount_rate: float,
) -> List[float]:
    return [
        _discount_to_present(fcf, discount_rate, i + 1)
        for i, fcf in enumerate(fcf_projections)
    ]


def compute_discounted_cash_flow(
    fcf_projections: List[float],
    discount_rate: float,
    terminal_growth_rate: float,
) -> DiscountedCashFlow:
    if discount_rate <= 0:
        raise ValueError("Discount rate must be positive.")
    if not fcf_projections:
        raise ValueError("At least one FCF projection is required.")

    pv_fcfs       = _present_value_of_fcfs(fcf_projections, discount_rate)
    pv_fcfs_total = safe_sum(*pv_fcfs)
    terminal_value = _terminal_value_gordon(
        fcf_projections, discount_rate, terminal_growth_rate
    )
    pv_terminal = _discount_to_present(terminal_value, discount_rate, len(fcf_projections))
    ev = safe_sum(pv_fcfs_total, pv_terminal)

    return DiscountedCashFlow(
        pv_fcfs=pv_fcfs,
        pv_fcfs_total=pv_fcfs_total,
        terminal_value=terminal_value,
        pv_terminal_value=pv_terminal,
        enterprise_value=ev,
    )


def _equity_weight(market_cap: Optional[float], total_value: float) -> float:
    result = safe_div(float(market_cap or 0.0), total_value)
    return result if result is not None else 0.0


def _debt_weight(total_debt: Optional[float], total_value: float) -> float:
    result = safe_div(float(total_debt or 0.0), total_value)
    return result if result is not None else 0.0


def _waac(
    equity_weight: float,
    cost_of_equity: float,
    debt_weight: float,
    cost_of_debt: float,
    tax_rate: float,
) -> float:
    return equity_weight * cost_of_equity + debt_weight * cost_of_debt * (1.0 - tax_rate)


def compute_wacc(
    market_cap: Optional[float],
    total_debt: Optional[float],
    cost_of_equity: float,
    cost_of_debt: Optional[float],
    tax_rate: Optional[float],
) -> WACC:
    equity      = float(market_cap or 0)
    debt        = float(total_debt or 0)
    total_value = equity + debt
    if total_value <= 0:
        raise ValueError("Total firm value (equity + debt) must be positive.")

    _cost_of_debt = float(cost_of_debt or 0)
    _tax_rate     = float(tax_rate or 0)
    eq_w   = _equity_weight(market_cap, total_value)
    de_w   = _debt_weight(total_debt, total_value)
    wacc_value = _waac(eq_w, cost_of_equity, de_w, _cost_of_debt, _tax_rate)

    return WACC(
        equity=equity,
        debt=debt,
        total_value=total_value,
        cost_of_equity=cost_of_equity,
        cost_of_debt=_cost_of_debt,
        tax_rate=_tax_rate,
        wacc=wacc_value,
    )
