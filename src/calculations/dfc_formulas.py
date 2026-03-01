from typing import List, Optional
from domain.metrics.valuation import DiscountedCashFlow, WACC
from .common import safe_div, safe_sum

def market_enterprise_value(
    market_cap: Optional[float],
    total_debt: Optional[float],
    cash_and_equivalents: Optional[float]
) -> float:
    """
    Compute market-implied enterprise value (EV) using primitive values.

    Formula:
        EV = Market Cap + Total Debt - Cash & Equivalents

    Args:
        market_cap: Market capitalization of the company.
        total_debt: Total debt from the balance sheet.
        cash_and_equivalents: Cash and equivalents from the balance sheet.

    Returns:
        Enterprise value as a float. All None inputs are treated as 0.0.
    """
    return safe_sum(market_cap, total_debt) - (cash_and_equivalents or 0.0)

def cost_of_equity_capm(
    risk_free_rate: float,
    beta: float,
    market_risk_premium: float
) -> float:
    """
    Cost of Equity calculation using the Capital Asset Pricing Model (CAPM).
    
    Formula:
        Re = Rf + \beta \times (R_m - R_f)

    Args:
        risk_free_rate: Risk-free rate (decimal) ($R_f$).
        beta: Stock beta ($\beta$).
        market_risk_premium: Market risk premium (Rm - Rf).

    Returns:
        Cost of equity (Re) as a decimal.
    """
    return risk_free_rate + beta * market_risk_premium


def intrinsic_value_per_share(enterprise_value: float, shares_outstanding: float) -> float:
    """
    Compute intrinsic value per share.

    Args:
        enterprise_value: Enterprise value from DCF valuation.
        shares_outstanding: Number of shares outstanding.

    Returns:
        Value per share.

    Raises:
        ValueError: If shares_outstanding is zero or negative.
    """
    if shares_outstanding <= 0:
        raise ValueError("Shares outstanding must be positive for value per share calculation.")
    return enterprise_value / shares_outstanding


def _discount_to_present(future_value: float, discount_rate: float, periods: int) -> float:
    """
    Compute present value (PV) of a future cash flow, assuming compounding is per period.

    Formula:
        $PV = \frac{FV}{(1 + r)^n}$

    Args:
        future_value: Future value of cash flow.
        discount_rate: Discount rate per period (as decimal, e.g., 0.10).
        periods: Number of periods (years) to discount back.

    Returns:
        Present value of the cash flow.

    Raises:
        ValueError: If periods is zero or negative.
    """
    if periods <= 0:
        raise ValueError("Periods must be greater than 0 for discounting.")
    
    discount_factor = (1.0 + discount_rate) ** periods
    return safe_div(future_value, discount_factor)


def _terminal_value_gordon(
    last_n_fcfs: List[float],
    discount_rate: float,
    terminal_growth_rate: float
) -> float:
    """
    Compute terminal value using the Gordon Growth Model.
    
    Formula:
        TV_n = \frac{FCF_{n+1}}{r - g} = \frac{FCF_{avg} \times (1 + g)}{r - g}

    Args:
        last_n_fcfs: Last few FCFs (up to 3) used to estimate FCF_n (the last year's FCF).
        discount_rate: Discount rate (WACC) ($r$).
        terminal_growth_rate: Long-term growth rate ($g$).

    Returns:
        Terminal value at the end of the forecast horizon.

    Raises:
        ValueError: If discount_rate <= terminal_growth_rate or last_n_fcfs is empty.
    """
    if discount_rate <= terminal_growth_rate:
        raise ValueError("Discount rate must be strictly greater than terminal growth rate.")
    if not last_n_fcfs:
        raise ValueError("At least one FCF is required for terminal value calculation.")

    n = min(3, len(last_n_fcfs))
    avg_fcf = sum(last_n_fcfs[-n:]) / float(n)
    
    fcf_n_plus_1 = avg_fcf * (1.0 + terminal_growth_rate)
    
    return fcf_n_plus_1 / (discount_rate - terminal_growth_rate)


def market_implied_wacc(
    target_enterprise_value: float,
    terminal_growth_rate: float,
    fcf_projections: List[float]
) -> float:
    """
    Reverse-engineer the implied WACC via binary search.
    Finds the discount rate that makes the Discounted Cash Flow (DCF) value approximately 
    equal to the target enterprise value.

    Args:
        target_enterprise_value: The current market-implied enterprise value.
        terminal_growth_rate: Terminal growth rate for the Gordon Growth Model (g).
        fcf_projections: List of forecasted free cash flows.

    Returns:
        Implied WACC (decimal), rounded to 6 decimal places.

    Raises:
        ValueError: If target enterprise value is non-positive or FCF projections list is empty.
    """
    if target_enterprise_value <= 0 or not fcf_projections:
        raise ValueError("Valid positive enterprise value and FCF projections list are required.")

    low = max(terminal_growth_rate + 1e-6, 1e-4)
    high = 1.0
    
    last_fcfs = fcf_projections[-3:]
    num_years = len(fcf_projections)

    for _ in range(100):
        mid = (low + high) / 2
        pv_fcfs = sum(_discount_to_present(fcf, mid, i + 1) for i, fcf in enumerate(fcf_projections))

        try:
            tv = _terminal_value_gordon(last_fcfs, mid, terminal_growth_rate)
        except ValueError:
            value = float('inf')
        else:
            pv_tv = _discount_to_present(tv, mid, num_years)
            value = pv_fcfs + pv_tv
        
        if value > target_enterprise_value:
            low = mid
        else:
            high = mid

    return round((low + high) / 2, 6)


def _present_value_of_fcfs(fcf_projections: List[float], discount_rate: float) -> List[float]:
    """
    Discount a list of FCF projections to their present value.

    Args:
        fcf_projections: List of forecasted free cash flows. The first element is FCF for year 1.
        discount_rate: Discount rate (decimal).

    Returns:
        List of the present value of each FCF projection.
    """
    return [
        _discount_to_present(fcf, discount_rate, i + 1)
        for i, fcf in enumerate(fcf_projections)
    ]


def compute_discounted_cash_flow(
    fcf_projections: List[float],
    discount_rate: float,
    terminal_growth_rate: float
) -> DiscountedCashFlow:
    """
    Compute discounted cash flow (DCF) with terminal value.

    Args:
        fcf_projections: List of forecasted FCFs.
        discount_rate: WACC for discounting.
        terminal_growth_rate: Terminal growth rate for TV.

    Returns:
        DiscountedCashFlowResult containing PVs and enterprise value.
    """
    if discount_rate <= 0:
        raise ValueError("Discount rate must be positive.")
    if not fcf_projections:
        raise ValueError("At least one FCF projection required.")

    pv_fcfs = _present_value_of_fcfs(fcf_projections, discount_rate)
    pv_fcfs_total = safe_sum(*pv_fcfs)
    terminal_value = _terminal_value_gordon(fcf_projections, discount_rate, terminal_growth_rate)
    pv_terminal = _discount_to_present(terminal_value, discount_rate, len(fcf_projections))
    _enterprise_value = safe_sum(pv_fcfs_total, pv_terminal)

    return DiscountedCashFlow(
        pv_fcfs=pv_fcfs,
        pv_fcfs_total=pv_fcfs_total,
        terminal_value=terminal_value,
        pv_terminal_value=pv_terminal,
        enterprise_value=_enterprise_value
    )


def _equity_weight(market_cap: Optional[float], total_value: float) -> float:
    """
    Calculate the equity weight in the firm's capital structure (E/V).

    Args:
        market_cap: Market capitalization (Equity value).
        total_value: Total firm value (Equity + Debt).

    Returns:
        Equity weight as a float, or 0.0 if total_value is zero.
    """
    equity = float(market_cap or 0.0)
    return safe_div(equity, total_value)


def _debt_weight(total_debt: Optional[float], total_value: float) -> float:
    """
    Calculate the debt weight in the firm's capital structure (D/V).

    Args:
        total_debt: Total debt.
        total_value: Total firm value (Equity + Debt).

    Returns:
        Debt weight as a float, or 0.0 if total_value is zero.
    """
    debt = float(total_debt or 0.0)
    return safe_div(debt, total_value)


def _waac(
    equity_weight: float,
    cost_of_equity: float,
    debt_weight: float,
    cost_of_debt: float,
    tax_rate: float
) -> float:
    """
    Compute the Weighted Average Cost of Capital (WACC).

    Formula:
        WACC = (E/V) * Re + (D/V) * Rd * (1 - Tc)

    Args:
        equity_weight: Weight of equity in the capital structure (E/V).
        cost_of_equity: Cost of equity (Re).
        debt_weight: Weight of debt in the capital structure (D/V).
        cost_of_debt: Cost of debt (Rd).
        tax_rate: Corporate tax rate (Tc).

    Returns:
        Weighted Average Cost of Capital as a float.
    """
    return equity_weight * cost_of_equity + debt_weight * cost_of_debt * (1.0 - tax_rate)


def compute_wacc(
    market_cap: Optional[float],
    total_debt: Optional[float],
    cost_of_equity: float,
    cost_of_debt: Optional[float],
    tax_rate: Optional[float]
) -> WACC:
    """
    Calculate the Weighted Average Cost of Capital (WACC) and all intermediate parameters.

    Formula:
        WACC = (E/V)*Re + (D/V)*Rd*(1 - Tc)

    Args:
        market_cap: Market capitalization (equity value).
        total_debt: Total debt.
        cost_of_equity: Cost of equity (Re) in decimal.
        cost_of_debt: Cost of debt (Rd) in decimal.
        tax_rate: Corporate tax rate (Tc) in decimal.

    Returns:
        WACCResult containing all intermediate values and the final WACC.
    """
    equity = float(market_cap or 0)
    debt = float(total_debt or 0)
    total_value = equity + debt

    if total_value <= 0:
        raise ValueError("Total firm value (equity + debt) must be positive.")
    
    cost_of_debt = float(cost_of_debt or 0)
    tax_rate = float(tax_rate or 0)

    equity_weight = _equity_weight(market_cap, total_value)
    debt_weight = _debt_weight(total_debt, total_value)
    wacc_value = _waac(
        equity_weight, cost_of_equity, debt_weight, cost_of_debt, tax_rate
    )

    return WACC(
        equity=equity,
        debt=debt,
        total_value=total_value,
        cost_of_equity=cost_of_equity,
        cost_of_debt=cost_of_debt,
        tax_rate=tax_rate,
        wacc=wacc_value
    )

