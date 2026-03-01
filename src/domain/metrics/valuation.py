from dataclasses import dataclass
from typing import List

@dataclass
class DiscountedCashFlow:
    pv_fcfs: List[float]
    pv_fcfs_total: float
    terminal_value: float
    pv_terminal_value: float
    enterprise_value: float

@dataclass
class WACC:
    equity: float
    debt: float
    total_value: float
    cost_of_equity: float
    cost_of_debt: float
    tax_rate: float
    wacc: float

