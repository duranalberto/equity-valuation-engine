"""
financial_repository.py — the repository protocol and field descriptor types.

Changes from the original
--------------------------
1. ``FinancialRepository`` is now ``@runtime_checkable`` so ``MetricsLoader``
   (and any future caller) can do ``isinstance(loader, FinancialRepository)``
   at construction time rather than discovering type mismatches at call-time.

2. ``get_highest_price``, ``get_price_history``, and ``get_eps_history`` are
   declared on the protocol.  They were previously called in ``MetricsLoader``
   but absent from the interface — a new data-source author would not know
   they were required.

3. ``get_eps_data_quality`` is added to the protocol so callers can inspect
   the provenance of EPS values without casting to a concrete type.
"""
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
    GET_LATEST_VALUE = 0
    GET_TTM_VALUE = 1
    GET_TTM_PREV_VALUE = 2


class Period(Enum):
    ANNUAL = "annual"
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
    * For ``Action.GET_LATEST_VALUE`` the parser respects ``period`` — it
      looks in the annual DataFrame when ``Period.ANNUAL`` is declared and in
      the quarterly DataFrame when ``Period.QUARTERLY`` is declared.
    * For ``Action.GET_TTM_VALUE`` and ``Action.GET_TTM_PREV_VALUE`` the parser
      always aggregates four consecutive *quarterly* rows regardless of
      ``period``.  ``period`` on a TTM field is therefore meaningless and
      should be left as ``None`` to avoid confusion.
    """

    label: List[str]
    statement: Statement
    action: Action
    period: Optional[Period] = None

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

    ``@runtime_checkable`` means ``isinstance(obj, FinancialRepository)``
    works at runtime, enabling early failure in ``MetricsLoader.__init__``
    rather than cryptic AttributeErrors later.

    Implementing a new source
    -------------------------
    1. Create a concrete mapper tree (subclass ``BaseStockMetricsMapper``).
    2. Create a loader class that implements every method below.
    3. Pass ``loader_cls=YourLoader`` to ``MetricsLoader``.

    No domain or application changes are needed.
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