from __future__ import annotations

import abc
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Union

from infrastructure.repositories.financial_repository import (
    LabelField, FinancialField, Statement, Action, Period,
)


class CurrencyType(Enum):
    FINANCIAL = "financial_currency"
    TRADING   = "trading_currency"
    NONE      = None


@dataclass(kw_only=True)
class CurrencyField(abc.ABC):
    currency_type: CurrencyType = CurrencyType.NONE


@dataclass(kw_only=True)
class YfLabelField(LabelField, CurrencyField):
    """
    Maps a StockMetrics field to one or more Yahoo Finance info-dict keys.

    ``label`` accepts either a plain string (single key) or a list of strings
    (tried in order, first match wins).
    """
    label: Union[str, List[str]]

    @property
    def labels(self) -> List[str]:
        """Always returns a list, regardless of how ``label`` was declared."""
        if isinstance(self.label, list):
            return self.label
        return [self.label]

    def validate(self) -> None:
        if not self.label:
            raise ValueError("Label cannot be empty.")
        if isinstance(self.label, list) and not all(self.label):
            raise ValueError("Label list must not contain empty strings.")


@dataclass(kw_only=True)
class YfFinancialField(FinancialField, CurrencyField):
    """
    Maps a StockMetrics scalar field to a row in a financial statement
    DataFrame.  ``action`` must be one of the scalar actions
    (GET_LATEST_VALUE, GET_TTM_VALUE, GET_TTM_PREV_VALUE).
    """
    label:     List[str]
    statement: Statement
    action:    Action
    period:    Optional[Period] = None

    def validate(self) -> None:
        if not isinstance(self.label, list) or not self.label:
            raise ValueError("Labels list cannot be empty.")


@dataclass(kw_only=True)
class YfSeriesField(FinancialField, CurrencyField):
    """
    Maps a history-companion field to a row in a financial statement
    DataFrame.  The loader always calls ``get_series()`` for this field type.

    ``action`` is fixed to ``Action.GET_SERIES`` and is set automatically;
    do not pass it in the constructor.

    ``period`` controls which DataFrame is queried (QUARTERLY or ANNUAL).
    When omitted the loader defaults to QUARTERLY.
    """
    label:     List[str]
    statement: Statement
    period:    Optional[Period] = None
    # action is always GET_SERIES — override the parent's required field
    action:    Action = field(default=Action.GET_SERIES, init=False)

    def validate(self) -> None:
        if not isinstance(self.label, list) or not self.label:
            raise ValueError("Labels list cannot be empty.")
