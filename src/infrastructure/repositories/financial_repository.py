import abc
from dataclasses import dataclass
from enum import Enum
from typing import Any, List, Optional, Protocol, runtime_checkable

from infrastructure.mappers.stock_metrics_mapper import BaseStockMetricsMapper


class Statement(Enum):
    INCOME = "income"
    CASHFLOW = "cashflow"
    BALANCE_SHEET = "balance_sheet"


class Action(Enum):
    GET_LATEST_VALUE  = 0
    GET_TTM_VALUE     = 1
    GET_TTM_PREV_VALUE = 2
    GET_SERIES        = 3


class Period(Enum):
    ANNUAL    = "annual"
    QUARTERLY = "quarterly"


class BaseField(abc.ABC):
    label: str

    @abc.abstractmethod
    def validate(self) -> None:
        pass


@dataclass(kw_only=True)
class EnumField(BaseField):
    label: str
    enum: Enum

    def validate(self) -> None:
        if not self.label:
            raise ValueError("Label cannot be empty.")


@dataclass(kw_only=True)
class LabelField(BaseField):
    label: str

    def validate(self) -> None:
        if not self.label:
            raise ValueError("Label cannot be empty.")


@dataclass(kw_only=True)
class FinancialField(BaseField):
    """
    Descriptor for a row inside a financial statement DataFrame.

    ``period`` usage
    ----------------
    * ``GET_LATEST_VALUE`` — respects ``period`` (annual vs quarterly DataFrame).
    * ``GET_TTM_VALUE`` / ``GET_TTM_PREV_VALUE`` — always aggregates four
      consecutive quarterly rows; ``period`` is ignored on these actions.
    * ``GET_SERIES`` — ``period`` controls which DataFrame is used.  When
      ``period`` is ``None`` the loader defaults to ``QUARTERLY``.

    Returns
    -------
    ``GET_SERIES`` returns ``Optional[List[float]]`` (oldest first).
    All other actions return ``Optional[float]``.
    """
    label:     List[str]
    statement: Statement
    action:    Action
    period:    Optional[Period] = None

    def validate(self) -> None:
        if not isinstance(self.label, list) or not self.label:
            raise ValueError("Labels list cannot be empty.")


# --------------------------------------------------------------------------- #
# Protocol
# --------------------------------------------------------------------------- #

@runtime_checkable
class FinancialRepository(Protocol):
    """
    The interface every data-source loader must implement.
    """

    mapper: BaseStockMetricsMapper

    def get_label(self, field: BaseField) -> Optional[Any]:
        """Resolve a scalar label from the info dict or equivalent."""
        ...

    def get_ttm_from_quarters(
        self, field: FinancialField, year_offset: int = 0
    ) -> Optional[float]:
        """Sum four consecutive quarterly values at the given year offset."""
        ...

    def get_annual_value(
        self, field: FinancialField, year_offset: int = 0
    ) -> Optional[float]:
        """Return the annual value at the given year offset (0 = most recent)."""
        ...

    def get_latest_numeric(self, field: FinancialField) -> Optional[float]:
        """Return the most recent single numeric value for the field."""
        ...

    def get_series(
        self,
        field: FinancialField,
        period: Optional[Period] = None,
    ) -> Optional[List[float]]:
        """
        Return all available values for a statement row as a list, oldest first.

        Parameters
        ----------
        field  : FinancialField descriptor (label / statement required;
                 ``action`` is ignored — the caller is explicitly requesting
                 a series).
        period : Override the granularity.  When ``None`` the loader uses
                 ``field.period`` if set, otherwise defaults to QUARTERLY.

        Returns
        -------
        ``List[float]`` ordered oldest-first, or ``None`` when no data is
        available.  An empty list is never returned.
        """
        ...

    def get_highest_price(self) -> Optional[float]:
        """Return the highest historical price in the loader's price series."""
        ...

    def get_price_history(self) -> Optional[List[float]]:
        """Return price history as a list of floats, oldest first."""
        ...

    def get_eps_history(self) -> Optional[List[float]]:
        """Return EPS history as a list of floats, oldest first."""
        ...

    def get_eps_data_quality(self) -> Any:
        """
        Return a ``DataQuality`` enum value indicating how EPS was derived.
        Typed as ``Any`` here to avoid a circular import with value_objects.
        """
        ...
