from __future__ import annotations

from enum import Enum, auto
from typing import Any, List, Optional, Protocol, Union, runtime_checkable


class Action(Enum):
    GET_LATEST_VALUE   = auto()
    GET_TTM_VALUE      = auto()
    GET_TTM_PREV_VALUE = auto()
    GET_SERIES         = auto()


class Period(Enum):
    QUARTERLY = "quarterly"
    ANNUAL    = "annual"


class BaseField:
    """Marker base class for all field descriptor types."""
    pass


class FinancialField(BaseField):
    """
    Descriptor for a numeric financial field.

    ``label``  — the exact column/row key expected in the source data frame.
    ``action`` — which loader method should handle this field.
    ``period`` — relevant only when action is ``GET_SERIES``.
    """

    def __init__(
        self,
        label: Union[str, List[str]],
        action: Action,
        period: Optional[Period] = None,
    ) -> None:
        self.label  = label
        self.action = action
        self.period = period

    def __repr__(self) -> str:
        return (
            f"FinancialField(label={self.label!r}, action={self.action.name}, "
            f"period={self.period})"
        )


class LabelField(BaseField):
    """Descriptor for a string-valued field (company name, exchange, etc.)."""

    def __init__(self, label: str) -> None:
        self.label = label

    def __repr__(self) -> str:
        return f"LabelField(label={self.label!r})"


class EnumField(BaseField):
    """Descriptor for an enum-valued field (sector, quote type, etc.)."""

    def __init__(self, label: str) -> None:
        self.label = label

    def __repr__(self) -> str:
        return f"EnumField(label={self.label!r})"


@runtime_checkable
class FinancialRepository(Protocol):
    """
    Protocol that every data-loader must satisfy.

    ``MetricsLoader`` depends only on this interface — no yfinance import
    in the application layer.
    """

    @property
    def mapper(self):
        """Return the ``StockMetricsMapper`` for this loader."""
        ...

    def get_label(
        self,
        field: Union[LabelField, EnumField],
    ) -> Optional[Union[str, Any]]:
        ...

    def get_ttm_from_quarters(
        self,
        field: FinancialField,
        year_offset: int = 0,
    ) -> Optional[float]:
        ...

    def get_annual_value(
        self,
        field: FinancialField,
        year_offset: int = 0,
    ) -> Optional[float]:
        ...

    def get_latest_numeric(
        self,
        field: FinancialField,
    ) -> Optional[float]:
        ...

    def get_series(
        self,
        field: FinancialField,
        period: Optional[Period] = None,
    ) -> Optional[List[float]]:
        ...

    def get_highest_price(self) -> Optional[float]:
        ...

    def get_price_history(self) -> Optional[List[float]]:
        ...

    def get_eps_history(self) -> Optional[List[float]]:
        ...