from __future__ import annotations

import logging
from typing import List, Optional, Union

import pandas as pd

logger = logging.getLogger(__name__)


def _to_float(value) -> Optional[float]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        result = float(value)
        return None if pd.isna(result) else result
    except (TypeError, ValueError):
        return None


def get_row_values(
    df: Optional[pd.DataFrame],
    label: Union[str, List[str]],
) -> Optional[pd.Series]:
    """
    Return the row matching *label* from *df*, or None.

    *label* may be a single string or a list of candidate labels tried in
    order — the first match wins.
    """
    if df is None or df.empty:
        return None

    labels = [label] if isinstance(label, str) else label

    for lbl in labels:
        if lbl in df.index:
            return df.loc[lbl]

    logger.debug("None of %r found in DataFrame index.", labels)
    return None


def get_ttm_from_quarters(
    df: Optional[pd.DataFrame],
    label: Union[str, List[str]],
    year_offset: int = 0,
) -> Optional[float]:
    """
    Sum four quarterly values ending ``year_offset * 4`` columns from the
    left (most-recent) to produce a trailing-twelve-months figure.
    """
    row = get_row_values(df, label)
    if row is None or len(row) < 4:
        return None

    start = year_offset * 4
    end   = start + 4
    if end > len(row):
        return None

    window = [_to_float(v) for v in row.iloc[start:end]]
    valid  = [v for v in window if v is not None]
    if len(valid) < 4:
        return None

    return sum(valid)


def get_annual_value(
    df: Optional[pd.DataFrame],
    label: Union[str, List[str]],
    year_offset: int = 0,
) -> Optional[float]:
    """Return the single annual column at *year_offset* from the most-recent."""
    row = get_row_values(df, label)
    if row is None or year_offset >= len(row):
        return None
    return _to_float(row.iloc[year_offset])


def get_latest_numeric(
    df: Optional[pd.DataFrame],
    label: Union[str, List[str]],
) -> Optional[float]:
    """Return the most-recent non-null value for *label*."""
    row = get_row_values(df, label)
    if row is None:
        return None
    for value in row:
        result = _to_float(value)
        if result is not None:
            return result
    return None


def get_series(
    df: Optional[pd.DataFrame],
    label: Union[str, List[str]],
    ascending: bool = True,
) -> Optional[List[float]]:
    """
    Return all non-null values for *label* as a list.

    When *ascending* is True (default) the list runs oldest → newest.
    """
    row = get_row_values(df, label)
    if row is None:
        return None

    values = [_to_float(v) for v in row]
    clean  = [v for v in values if v is not None]
    if not clean:
        return None

    return list(reversed(clean)) if ascending else clean
