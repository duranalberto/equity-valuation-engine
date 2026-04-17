import math
from typing import List, Optional, Union

from domain.core.missing import Missing

from .common import safe_div, safe_sum


def enterprise_value(
    market_cap: Optional[float] | Missing,
    total_debt: Optional[float] | Missing,
    cash: Optional[float] | Missing,
) -> Optional[float] | Missing:
    if isinstance(market_cap, Missing):
        return market_cap
    if isinstance(total_debt, Missing):
        return total_debt
    if isinstance(cash, Missing):
        return cash
    if market_cap is None:
        return None
    combined = safe_sum(market_cap, total_debt)
    if isinstance(combined, Missing) or combined is None:
        return combined
    return combined - (cash or 0.0)


def interest_coverage(
    ebit_ttm: Optional[float] | Missing,
    interest_exp_ttm: Optional[float] | Missing,
) -> Optional[float] | Missing:
    if interest_exp_ttm is None or interest_exp_ttm == 0:
        return None
    return safe_div(ebit_ttm, abs(interest_exp_ttm))


def quick_ratio(
    current_assets: Optional[float] | Missing,
    inventory: Optional[float] | Missing,
    current_liabilities: Optional[float] | Missing,
) -> Optional[float] | Missing:
    if isinstance(current_assets, Missing):
        return current_assets
    if isinstance(inventory, Missing):
        return inventory
    if isinstance(current_liabilities, Missing):
        return current_liabilities
    if current_assets is None or current_liabilities is None:
        return None
    numerator = float(current_assets) - float(inventory or 0.0)
    return safe_div(numerator, current_liabilities)


def dividend_yield(
    dividends_paid_ttm: Optional[float] | Missing,
    shares_outstanding: Optional[float] | Missing,
    current_price: Optional[float] | Missing,
) -> Optional[float] | Missing:
    dps = safe_div(abs(dividends_paid_ttm or 0.0), shares_outstanding)
    if dps is None:
        return None
    return safe_div(dps, current_price)


def payout_ratio(
    dividends_paid_ttm: Optional[float] | Missing,
    net_income_ttm: Optional[float] | Missing,
) -> Optional[float] | Missing:
    return safe_div(abs(dividends_paid_ttm or 0.0), net_income_ttm)


def price_to_book(
    price: Optional[float] | Missing,
    total_equity: Optional[float] | Missing,
    shares_outstanding: Optional[Union[float, int]] | Missing,
) -> Optional[float] | Missing:
    if isinstance(price, Missing):
        return price
    if isinstance(total_equity, Missing):
        return total_equity
    if isinstance(shares_outstanding, Missing):
        return shares_outstanding
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
    if start < 0 < end or end < 0 < start:
        return None
    try:
        result = (end / start) ** (1.0 / (len(values) - 1)) - 1.0
    except Exception:
        return None
    if isinstance(result, complex) or not math.isfinite(result):
        return None
    return float(result)


def median_pe_ratio(
    prices: List[float],
    eps_values: List[float],
) -> Optional[float]:
    """
    Compute the median historical P/E from parallel price and EPS lists.

    The lists are still zipped positionally (oldest-first), so the caller is
    responsible for ensuring they cover the same time window and granularity.
    Mismatched lengths are handled by truncating to the shorter list, as
    before.
    """
    if not prices or not eps_values:
        return None

    min_len = min(len(prices), len(eps_values))

    pe_series = [
        p / e
        for p, e in zip(prices[:min_len], eps_values[:min_len])
        if e is not None and e > 0 and p is not None and p > 0
    ]

    if len(pe_series) < 3:
        return None

    sorted_pe = sorted(pe_series)
    n = len(sorted_pe)
    q1 = sorted_pe[n // 4]
    q3 = sorted_pe[(3 * n) // 4]
    iqr = q3 - q1
    fence_low  = q1 - 3.0 * iqr
    fence_high = q3 + 3.0 * iqr
    filtered = [v for v in sorted_pe if fence_low <= v <= fence_high]

    if len(filtered) < 3:
        filtered = sorted_pe

    n2 = len(filtered)
    mid = n2 // 2
    if n2 % 2 == 1:
        return filtered[mid]
    return (filtered[mid - 1] + filtered[mid]) / 2.0


def calculate_growth(
    current_value: Optional[float] | Missing,
    previous_value: Optional[float] | Missing,
) -> Optional[float] | Missing:
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
    invested_capital = safe_sum(total_debt, total_equity)
    if isinstance(invested_capital, Missing) or invested_capital is None:
        return invested_capital
    invested_capital = invested_capital - (cash_and_equivalents or 0.0)
    if invested_capital == 0:
        return None
    nopat = ebit_ttm * (1.0 - (tax_rate or 0.0))
    return safe_div(nopat, invested_capital)
