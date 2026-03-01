import abc
from enum import Enum
from dataclasses import dataclass
from typing import List, Optional
from infrastructure.repositories.financial_repository import (
    LabelField, FinancialField, Statement,
    Action, Period
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
    Extends LabelField to include a currency_type. 
    Inherits 'label' from LabelField.
    """
    label: str

    def validate(self) -> None:
        """Implements the validation check from BaseField/LabelField."""
        if not self.label:
            raise ValueError("Label cannot be empty.")


@dataclass(kw_only=True)
class YfFinancialField(FinancialField, CurrencyField):
    """
    Extends FinancialField to include a currency_type.
    Inherits 'label', 'statement', 'action', and 'period' from FinancialField.
    """
    label: List[str]
    statement: Statement
    action: Action
    period: Optional[Period] = None
    
    def validate(self) -> None:
        """Implements the validation check from BaseField/FinancialField."""
        if not isinstance(self.label, list) or not self.label:
            raise ValueError("Labels list cannot be empty.")

