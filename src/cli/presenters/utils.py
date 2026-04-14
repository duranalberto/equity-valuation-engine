from enum import Enum

class colors(Enum):
    GREEN = "\033[32m"
    RED = "\033[31m"
    RESET = "\033[0m"

def fmt_num(x):
    return f"{x:,.2f}" if isinstance(x, (int, float)) and x is not None else "-"

def fmt_pct(x):
    return f"{x * 100:.2f}%" if isinstance(x, (int, float)) and x is not None else "-"
