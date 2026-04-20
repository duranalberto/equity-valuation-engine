from typing import Optional


def safe_div(
    numerator: Optional[float],
    denominator: Optional[float],
) -> Optional[float]:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return float(numerator) / float(denominator)


def safe_sum(*args: Optional[float]) -> float:
    return sum(float(a) for a in args if a is not None)
