from typing import Optional


def safe_div(
    numerator: Optional[float],
    denominator: Optional[float],
) -> Optional[float]:
    """
    Perform safe division.

    Returns:
        float  — result of numerator / denominator.
        None   — if either input is None OR the denominator is zero.

    Rationale: returning 0.0 on null inputs is financially incorrect.
    A gross-margin of 0.0 is a real, meaningful value. None means
    "this ratio could not be calculated". Callers that genuinely need
    a numeric default should write ``safe_div(...) or 0.0`` explicitly,
    making the intent visible at the call site.
    """
    if numerator is None or denominator is None or denominator == 0:
        return None
    return float(numerator) / float(denominator)


def safe_sum(*args: Optional[float]) -> float:
    """
    Safely compute the sum of optional floats, treating None as 0.0.

    NOTE: safe_sum always returns a float (never None) because a sum
    over an empty or all-None sequence is unambiguously 0.0 — unlike a
    ratio, there is no meaningful distinction between "zero" and "not
    calculated" for a running total.
    """
    return sum(float(a) for a in args if a is not None)