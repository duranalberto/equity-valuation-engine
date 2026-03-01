from typing import Optional


def safe_div(numerator: Optional[float], denominator: Optional[float]) -> float:
    """
    Perform safe division. Returns 0.0 if denominator is zero or any input is None.
    
    This prevents division-by-zero errors and downstream errors like 'NoneType.__format__' 
    when the result is used in formatting or reporting.

    Args:
        numerator: The numerator.
        denominator: The denominator.

    Returns:
        Result of numerator / denominator, or 0.0 if the calculation is invalid 
        (e.g., denominator is zero or an input is None).
    """
    if numerator is None or denominator in (None, 0):
        return 0.0
    
    return float(numerator) / float(denominator)


def safe_sum(*args: Optional[float]) -> float:
    """
    Safely computes the sum of a variable number of optional float arguments.

    If an argument is None, it is treated as 0.0 for the summation.

    Args:
        *args: A variable list of float or Optional[float] values.

    Returns:
        The sum of the values as a float.
    """
    total = 0.0
    for arg in args:
        total += float(arg) if arg is not None else 0.0
    return total

