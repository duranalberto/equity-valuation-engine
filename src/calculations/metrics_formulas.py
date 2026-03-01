from typing import Optional, List, Union
from .common import safe_div, safe_sum

def enterprise_value(
    market_cap: Optional[float],
    total_debt: Optional[float],
    cash: Optional[float]
) -> float:
    """
    Calculate Enterprise Value (EV).

    Formula:
        EV = Market Cap + Total Debt - Cash & Equivalents

    Args:
        market_cap: Market capitalization.
        total_debt: Total debt.
        cash: Cash and equivalents.

    Returns:
        Enterprise value as a float. Returns 0.0 if all inputs are None, 
        but handles partial None inputs by treating them as 0.0.
    """
    return safe_sum(market_cap, total_debt) - (cash or 0.0)


def interest_coverage(ebit_ttm: Optional[float], interest_exp_ttm: Optional[float]) -> float:
    """
    Calculates Interest Coverage ratio.

    Formula:
        Interest Coverage = EBIT / Interest Expense (absolute value)

    Args:
        ebit_ttm: Earnings Before Interest and Taxes (TTM).
        interest_exp_ttm: Interest Expense (TTM).

    Returns:
        Interest Coverage ratio, or 0.0 on failure (e.g., if denominator is zero or input is None).
    """
    denominator = abs(interest_exp_ttm) if interest_exp_ttm is not None else 0.0
    
    return safe_div(ebit_ttm, denominator)


def quick_ratio(
    current_assets: Optional[float], 
    inventory: Optional[float], 
    current_liabilities: Optional[float]
) -> float:
    """
    Calculate Quick Ratio (Acid-Test Ratio).

    Formula:
        Quick Ratio = (Current Assets - Inventory) / Current Liabilities

    Args:
        current_assets: Current assets.
        inventory: Inventory.
        current_liabilities: Current liabilities.

    Returns:
        Quick ratio as a float, or 0.0 if the calculation is invalid.
    """
    numerator = safe_sum(current_assets) - (inventory or 0.0)
    
    return safe_div(numerator, current_liabilities)


def dividend_yield(
    dividends_paid_ttm: Optional[float], 
    shares_outstanding: Optional[float], 
    current_price: Optional[float]
) -> float:
    """
    Calculate Dividend Yield.

    Formula:
        Dividend Yield = (Dividends Paid / Shares Outstanding) / Current Price

    Args:
        dividends_paid_ttm: Total dividends paid over the trailing twelve months (TTM).
        shares_outstanding: Number of shares outstanding.
        current_price: Current market price per share.

    Returns:
        Dividend yield as a decimal (e.g., 0.03 for 3%), or 0.0 if inputs are invalid.
    """
    dividends_per_share = safe_div(abs(dividends_paid_ttm or 0.0), shares_outstanding)
    return safe_div(dividends_per_share, current_price)


def payout_ratio(dividends_paid_ttm: Optional[float], net_income_ttm: Optional[float]) -> float:
    """
    Calculate Payout Ratio.

    Formula:
        Payout Ratio = Total Dividends / Net Income

    Args:
        dividends_paid_ttm: Total dividends paid over the trailing twelve months (TTM).
        net_income_ttm: Net income over the trailing twelve months (TTM).

    Returns:
        Payout ratio as a decimal, or 0.0 if the calculation is invalid.
    """
    return safe_div(abs(dividends_paid_ttm or 0.0), net_income_ttm)


def price_to_book(
    price: Optional[float],
    total_equity: Optional[float],
    shares_outstanding: Optional[Union[float, int]]
) -> float:
    """
    Calculate Price-to-Book (P/B) Ratio.

    Formula:
        P/B = Price / (Total Equity / Shares Outstanding)

    Args:
        price: Current market price per share.
        total_equity: Total book value of equity.
        shares_outstanding: Number of shares outstanding.

    Returns:
        Price-to-Book ratio as a float, or 0.0 if inputs are invalid.
    """
    if price is None or total_equity is None or shares_outstanding is None:
        return 0.0
    
    book_value_per_share = safe_div(total_equity, shares_outstanding)
    
    return safe_div(price, book_value_per_share)


def cagr_from_series(values: list[float]) -> Optional[float]:
    """
    Computes Compound Annual Growth Rate (CAGR) from a sequence of values.
    
    Formula:
        $CAGR = (\frac{Value_{End}}{Value_{Start}})^{1/n} - 1$

    Args:
        values: A sequence of historical values (e.g., EPS, FCF). Must contain at least two values.

    Returns:
        float: CAGR value (e.g. 0.12 for 12%) as a decimal.
        None: If the data is invalid, insufficient, or calculation fails (e.g., non-positive start/end values).
    """
    if not values or len(values) < 2:
        return None

    start = values[0]
    end = values[-1]
    
    if start is None or end is None or start == 0 or end == 0:
        return None

    try:
        n_periods = len(values) - 1
        return (end / start) ** (1.0 / n_periods) - 1.0
    except Exception:
        return None


def median_pe_ratio(prices: List[float], eps_values: List[float]) -> Optional[float]:
    """
    Computes the median historical Price-to-Earnings (P/E) ratio.

    Handles differing list lengths by truncating to the shorter list.

    Args:
        prices: Historical price series.
        eps_values: Historical Earnings Per Share (EPS) series.

    Returns:
        float: Median P/E ratio.
        None: If input is invalid or a meaningful median cannot be computed 
              (e.g., not enough positive EPS values).
    """

    if not prices or not eps_values:
        return None

    min_len = min(len(prices), len(eps_values))
    truncated_prices = prices[:min_len]
    truncated_eps = eps_values[:min_len]

    pe_series = [
        price / eps for price, eps in zip(truncated_prices, truncated_eps)
        if eps is not None and eps > 0
    ]

    if not pe_series:
        return None

    sorted_vals = sorted(pe_series)
    n = len(sorted_vals)
    mid = n // 2

    if n % 2 == 1:
        return sorted_vals[mid]
    else:
        return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2.0


def calculate_growth(current_value: Optional[float], previous_value: Optional[float]) -> float:
    """
    Calculates the period-over-period growth rate.

    Formula:
        Growth = (Current Value / Previous Value) - 1.0

    Args:
        current_value: The value at the end of the period.
        previous_value: The value at the start of the period.

    Returns:
        The growth rate as a decimal (e.g., 0.10 for 10%), or 0.0 if inputs are invalid.
    """
    return safe_div(current_value, previous_value) - 1.0


def roic(
    ebit_ttm: Optional[float],
    tax_rate: Optional[float],
    total_debt: Optional[float],
    total_equity: Optional[float],
    cash_and_equivalents: Optional[float]
) -> float:
    """
    Calculate Return on Invested Capital (ROIC).

    Formulas:
        NOPAT = EBIT \times (1 - Tax Rate)
        Invested Capital (IC) = Total Debt + Total Equity - Cash \& Equivalents
        ROIC = NOPAT / IC

    Args:
        ebit_ttm: Earnings before interest and taxes (TTM).
        tax_rate: Effective tax rate (0-1).
        total_debt: Total debt.
        total_equity: Total equity.
        cash_and_equivalents: Cash and equivalents.

    Returns:
        ROIC as a decimal, or 0.0 if inputs are invalid or the calculation is invalid.
    """

    invested_capital = safe_sum(total_debt, total_equity) - (cash_and_equivalents or 0.0)
    
    tax_rate_val = tax_rate if tax_rate is not None else 0.0
    nopat = (ebit_ttm or 0.0) * (1.0 - tax_rate_val)

    return safe_div(nopat, invested_capital)

