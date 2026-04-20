from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import pandas as pd


@dataclass
class RawTickerData:
    """
    Container for all raw data fetched from yfinance for a single ticker.

    All fields are Optional — a missing attribute from yfinance is stored as
    None rather than raising.
    """

    ticker:           str
    info:             Optional[Dict[str, Any]]            = None
    income_stmt_q:    Optional[pd.DataFrame]              = None
    income_stmt_a:    Optional[pd.DataFrame]              = None
    balance_sheet_q:  Optional[pd.DataFrame]              = None
    balance_sheet_a:  Optional[pd.DataFrame]              = None
    cash_flow_q:      Optional[pd.DataFrame]              = None
    cash_flow_a:      Optional[pd.DataFrame]              = None
    history:          Optional[pd.DataFrame]              = None
    fast_info:        Optional[Any]                       = None
