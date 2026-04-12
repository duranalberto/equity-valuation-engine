"""
Yfinance-specific field descriptor types.

Design 6: ``YfLabelField.label`` now accepts ``Union[str, List[str]]``.
Previously, multi-label fallback was expressed as a comma-separated string
(e.g. ``"averageVolume,averageDailyVolume10Day"``), which was an undocumented
convention hidden inside ``get_label``.  Changing to an explicit list type
makes the multi-label intent visible at the definition site and removes the
string-splitting logic from the lookup path.

The ``labels`` property normalises both forms to ``List[str]`` so all
consumers use a single code path regardless of how the label was declared.
"""
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
    TRADING = "trading_currency"
    NONE = None


@dataclass(kw_only=True)
class CurrencyField(abc.ABC):
    currency_type: CurrencyType = CurrencyType.NONE


@dataclass(kw_only=True)
class YfLabelField(LabelField, CurrencyField):
    """
    Maps a StockMetrics field to one or more Yahoo Finance info-dict keys.

    ``label`` accepts either a plain string (single key) or a list of strings
    (tried in order, first match wins).  The old comma-separated string syntax
    is no longer supported; update any existing usages to use a list instead.

    Examples::

        # Single label — unchanged from before
        YfLabelField(label="currentPrice", currency_type=CurrencyType.TRADING)

        # Multi-label fallback — previously: "averageVolume,averageDailyVolume10Day"
        YfLabelField(
            label=["averageVolume", "averageDailyVolume10Day"],
            currency_type=CurrencyType.TRADING,
        )
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
    Maps a StockMetrics field to one or more rows in a financial statement
    DataFrame.  Label semantics are unchanged: a list of candidate row names
    tried in order.
    """
    label: List[str]
    statement: Statement
    action: Action
    period: Optional[Period] = None

    def validate(self) -> None:
        if not isinstance(self.label, list) or not self.label:
            raise ValueError("Labels list cannot be empty.")