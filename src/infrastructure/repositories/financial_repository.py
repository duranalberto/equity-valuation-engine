import abc
from dataclasses import dataclass
from enum import Enum
from typing import Protocol, List, Optional, Any
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
    label: List[str]
    statement: Statement
    action: Action
    period: Optional[Period] = None
    
    def validate(self) -> None:
        if not isinstance(self.label, list) or not self.label:
            raise ValueError("Labels list cannot be empty.")
    

class FinancialRepository(Protocol):
    mapper: BaseStockMetricsMapper 
    
    def get_label(self, label: BaseField) -> Any:
        ...
        
    def get_ttm_from_quarters(self, field: FinancialField, year_offset=0) -> Optional[float]:
        ...
    
    def get_annual_value(self, field: FinancialField, year_offset=0) -> Optional[float]:
        ...
        
    def get_latest_numeric(self, field: FinancialField) -> Optional[float]:
        ...
    
    def get_highest_price(self) -> Optional[float]:
        ...

    def get_price_history(self) -> Optional[List[float]]:
        ...

    def get_eps_history(self) -> Optional[List[float]]:
        ...

