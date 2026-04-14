from typing import Optional, List, Union
from .common import safe_div, safe_sum


def enterprise_value(
    market_cap: Optional[float],
    total_debt: Optional[float],
    cash: Optional[float],
) -> Optional[float]:
    if market_cap is None:
        return None
    return safe_sum(market_cap, total_debt) - (cash or 0.0)


def interest_coverage(
    ebit_ttm: Optional[float],
    interest_exp_ttm: Optional[float],
) -> Optional[float]:
    if interest_exp_ttm is None or interest_exp_ttm == 0:
        return None
    return safe_div(ebit_ttm, abs(interest_exp_ttm))


def quick_ratio(
    current_assets: Optional[float],
    inventory: Optional[float],
    current_liabilities: Optional[float],
) -> Optional[float]:
    if current_assets is None or current_liabilities is None:
        return None
    numerator = current_assets - (inventory or 0.0)
    return safe_div(numerator, current_liabilities)


def dividend_yield(
    dividends_paid_ttm: Optional[float],
    shares_outstanding: Optional[float],
    current_price: Optional[float],
) -> Optional[float]:
    dps = safe_div(abs(dividends_paid_ttm or 0.0), shares_outstanding)
    if dps is None:
        return None
    return safe_div(dps, current_price)


def payout_ratio(
    dividends_paid_ttm: Optional[float],
    net_income_ttm: Optional[float],
) -> Optional[float]:
    return safe_div(abs(dividends_paid_ttm or 0.0), net_income_ttm)


def price_to_book(
    price: Optional[float],
    total_equity: Optional[float],
    shares_outstanding: Optional[Union[float, int]],
) -> Optional[float]:
    if price is None or total_equity is None or shares_outstanding is None:
        return None
    book_value_per_share = safe_div(total_equity, float(shares_outstanding))
    return safe_div(price, book_value_per_share)


def cagr_from_series(values: List[float]) -> Optional[float]:
    if not values or len(values) < 2:
        return None
    start, end = values[0], values[-1]
    if start is None or end is None or start == 0 or end == 0:
        return None
    try:
        return (end / start) ** (1.0 / (len(values) - 1)) - 1.0
    except Exception:
        return None


def median_pe_ratio(
    prices: List[float],
    eps_values: List[float],
) -> Optional[float]:
    if not prices or not eps_values:
        return None
    min_len = min(len(prices), len(eps_values))
    pe_series = [
        p / e
        for p, e in zip(prices[:min_len], eps_values[:min_len])
        if e is not None and e > 0
    ]
    if not pe_series:
        return None
    sorted_vals = sorted(pe_series)
    n = len(sorted_vals)
    mid = n // 2
    return sorted_vals[mid] if n % 2 == 1 else (sorted_vals[mid - 1] + sorted_vals[mid]) / 2.0


def calculate_growth(
    current_value: Optional[float],
    previous_value: Optional[float],
) -> Optional[float]:
    result = safe_div(current_value, previous_value)
    if result is None:
        return None
    return result - 1.0


def roic(
    ebit_ttm: Optional[float],
    tax_rate: Optional[float],
    total_debt: Optional[float],
    total_equity: Optional[float],
    cash_and_equivalents: Optional[float],
) -> Optional[float]:
    if ebit_ttm is None:
        return None
    invested_capital = safe_sum(total_debt, total_equity) - (cash_and_equivalents or 0.0)
    if invested_capital == 0:
        return None
    nopat = ebit_ttm * (1.0 - (tax_rate or 0.0))
    return safe_div(nopat, invested_capital)
