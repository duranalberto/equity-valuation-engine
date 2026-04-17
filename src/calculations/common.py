from typing import TypeAlias

from domain.core.missing import Missing, MissingReason

FinancialValue: TypeAlias = float | Missing | None


def safe_div(
    numerator: FinancialValue,
    denominator: FinancialValue,
    result_field: str = "",
) -> FinancialValue:
    if isinstance(numerator, Missing):
        return numerator
    if isinstance(denominator, Missing):
        return denominator
    if numerator is None or denominator is None:
        return None
    if denominator == 0:
        return Missing(MissingReason.INVALID_INPUT, result_field or "division")
    return float(numerator) / float(denominator)


def safe_sum(*args: FinancialValue) -> FinancialValue:
    total = 0.0
    saw_value = False
    for a in args:
        if isinstance(a, Missing):
            return a
        if a is not None:
            total += float(a)
            saw_value = True
    return total if saw_value else None
