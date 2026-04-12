"""
DataFrame utility functions for extracting financial data from yfinance output.

Fix 2   ``get_ordered_numeric_series`` now accepts an ``already_normalized``
        flag (default ``True`` since ``YfinanceDataLoader`` pre-normalizes all
        DataFrames at construction time).  Passing ``already_normalized=True``
        skips the ``normalize_df_index`` call, removing the 20+ redundant
        normalizations that previously happened on every field access.

        The flag defaults to ``True`` to match the new loader behaviour.
        Pass ``False`` when calling from code that has NOT pre-normalized.

Design 8  ``calculate_ttm_from_series`` now validates that the four selected
        quarters span approximately 9–12 months (i.e. they are not duplicates
        or large gaps caused by restated data).  A warning is logged and None
        returned when the date span is out of range, rather than silently
        summing mismatched quarters.
"""
from __future__ import annotations

import logging
import re
from typing import Optional, Iterable, Any, Union, List

import pandas as pd

logger = logging.getLogger(__name__)


def normalize_label(label: Any) -> str:
    """Normalise arbitrary strings into stable match keys."""
    s = re.sub(r"[^a-zA-Z0-9]+", "_", str(label).lower())
    return re.sub(r"_+", "_", s).strip("_")


def normalize_df_index(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return a copy of ``df`` with its index normalised via ``normalize_label``.
    Does not mutate ``df`` in place.
    """
    if df is None or df.empty:
        return df
    new_df = df.copy()
    try:
        new_df.index = [normalize_label(i) for i in new_df.index]
    except Exception:
        pass
    return new_df


def _find_matching_index(
    df: pd.DataFrame, normalized_candidates: Iterable[str]
) -> Optional[str]:
    """Strict match: normalized_candidate == normalized_df_index_label."""
    if df is None or df.empty:
        return None
    index_norm_map = {normalize_label(idx): idx for idx in df.index}
    for cand in normalized_candidates:
        nc = normalize_label(cand)
        if nc in index_norm_map:
            return index_norm_map[nc]
    return None


def _find_matching_column(
    df: pd.DataFrame, normalized_candidates: Iterable[str]
) -> Optional[str]:
    """Strict match: normalized_candidate == normalized_df_column_label."""
    if df is None or df.empty:
        return None
    col_norm_map = {normalize_label(c): c for c in df.columns}
    for cand in normalized_candidates:
        nc = normalize_label(cand)
        if nc in col_norm_map:
            return col_norm_map[nc]
    return None


def _order_df_columns_by_date(df: pd.DataFrame, descending: bool = True) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    cols = list(df.columns)
    parsed = {}
    for c in cols:
        try:
            parsed[c] = pd.to_datetime(str(c), errors="coerce")
        except Exception:
            parsed[c] = pd.NaT
    datetimes = [v for v in parsed.values() if not pd.isna(v)]
    if not datetimes:
        return df
    sortable = [(c, parsed[c]) for c in cols if not pd.isna(parsed[c])]
    unsortable = [c for c in cols if pd.isna(parsed[c])]
    sortable_sorted = sorted(sortable, key=lambda x: x[1], reverse=descending)
    return df.reindex(columns=[c for c, _ in sortable_sorted] + unsortable)


def _extract_numeric_row(df: pd.DataFrame, idx: Any) -> pd.Series:
    if df is None or df.empty or idx not in df.index:
        return pd.Series(dtype=float)
    row = pd.to_numeric(df.loc[idx], errors="coerce").dropna()
    if row.empty:
        return row
    try:
        dt_index = pd.to_datetime(row.index, errors="raise")
        return row.loc[dt_index.sort_values().index]
    except Exception:
        pass
    try:
        return row.sort_index()
    except Exception:
        return row


def extract_from_dataframe(
    df: pd.DataFrame,
    candidates: list,
    from_index: bool = False,
    as_list: bool = False,
) -> Optional[Union[pd.Series, list]]:
    """Strict deterministic extractor for a row or column."""
    if df is None or df.empty:
        return None
    df_norm = normalize_df_index(df)
    if from_index:
        match_key = _find_matching_index(df_norm, candidates)
        if match_key is None:
            return None
        series = pd.to_numeric(df_norm.loc[match_key], errors="coerce")
    else:
        match_key = _find_matching_column(df, candidates)
        if match_key is None:
            return None
        series = pd.to_numeric(df[match_key], errors="coerce")
    series = series.dropna()
    if as_list:
        xs = series.tolist()
        return xs if xs else None
    return series if not series.empty else None


def _flatten_and_clean_numeric(values: list) -> list:
    cleaned = []
    for v in values:
        try:
            numeric = pd.to_numeric(v, errors="coerce")
        except Exception:
            continue
        if hasattr(numeric, "__iter__") and not isinstance(numeric, (str, bytes)):
            cleaned.extend([float(x) for x in numeric if pd.notna(x)])
        else:
            if pd.notna(numeric):
                cleaned.append(float(numeric))
    return cleaned


def extract_sorted_numeric_column(
    df: pd.DataFrame,
    date_col: str,
    numeric_candidates: list,
) -> Optional[list]:
    if df is None or df.empty:
        return None
    df = df.copy()
    if date_col in df.columns:
        try:
            df["__dt"] = pd.to_datetime(df[date_col], errors="coerce")
            df = df.sort_values("__dt")
        except Exception:
            pass
    matched_col = _find_matching_column(df, numeric_candidates)
    if matched_col:
        xs = pd.to_numeric(df[matched_col], errors="coerce").dropna().tolist()
        return xs if xs else None
    for col in df.columns:
        if col == "__dt":
            continue
        numeric = pd.to_numeric(df[col], errors="coerce").dropna()
        if not numeric.empty:
            return numeric.tolist()
    return None


def _find_row_index(df: pd.DataFrame, labels: list) -> Optional[Any]:
    return _find_matching_index(df, labels)


def _extract_ordered_row(row: pd.Series, descending: bool = True) -> pd.Series:
    if row is None or row.empty:
        return row
    row_df = pd.DataFrame([row])
    row_df = _order_df_columns_by_date(row_df, descending=descending)
    return row_df.iloc[0]


def get_ordered_numeric_series(
    df: pd.DataFrame,
    labels: Union[List[str], str],
    already_normalized: bool = True,
) -> Optional[pd.Series]:
    """
    Find a row by label and return its numeric values ordered by date (descending).

    Fix 2: ``already_normalized`` defaults to ``True`` because
    ``YfinanceDataLoader`` pre-normalizes all DataFrames at construction.
    When ``True`` the ``normalize_df_index`` call is skipped entirely, removing
    the per-call overhead that was previously multiplied across every field lookup.

    Pass ``already_normalized=False`` from any code path that has not
    pre-normalized the DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        The financial statement DataFrame.
    labels : str | List[str]
        Row label candidates (tried in order).
    already_normalized : bool
        When True (default), assume the index is already normalized and skip
        the ``normalize_df_index`` step.

    Returns
    -------
    pd.Series of numeric values ordered descending by date, or None.
    """
    if df is None or df.empty:
        return None

    label_list = [labels] if isinstance(labels, str) else labels

    # Fix 2: skip normalization when the DataFrame was pre-normalized in __init__.
    working_df = df if already_normalized else normalize_df_index(df)

    idx = _find_row_index(working_df, label_list)
    if idx is None or idx not in working_df.index:
        return None

    row = _extract_numeric_row(working_df, idx)
    if row.empty or row.isna().all():
        return None

    ordered = _extract_ordered_row(row, descending=True)
    numeric = pd.to_numeric(ordered, errors="coerce").dropna()
    return numeric if not numeric.empty else None


# ---------------------------------------------------------------------------
# TTM calculation with date-span validation (Design 8)
# ---------------------------------------------------------------------------

_TTM_MIN_DAYS = 270   # ~9 months  — below this, quarters are too close together
_TTM_MAX_DAYS = 400   # ~13 months — above this, there may be a gap or restatement


def calculate_ttm_from_series(
    series: pd.Series,
    year_offset: int,
) -> Optional[float]:
    """
    Sum the four quarters that make up TTM at the requested offset.

    The series must be ordered descending by date (most recent first).

    Fix 2 / Design 8: After selecting the four quarters, we attempt to parse
    the column labels as dates.  When they are parseable, we validate that the
    span from the oldest to the newest selected quarter is between
    ``_TTM_MIN_DAYS`` (~9 months) and ``_TTM_MAX_DAYS`` (~13 months).  If the
    span is outside this range, a warning is logged and None is returned rather
    than silently summing mismatched or gapped data.

    When column labels are not parseable as dates (e.g. integer indices), the
    span check is skipped and behaviour is identical to before.

    Parameters
    ----------
    series : pd.Series
        Quarterly numeric values, ordered descending (most recent first).
    year_offset : int
        0 = latest TTM, 1 = previous TTM (one year prior), etc.

    Returns
    -------
    float (TTM sum) or None when insufficient or suspect data.
    """
    needed = (year_offset + 1) * 4
    if len(series) < needed:
        return None

    start = year_offset * 4
    end = start + 4
    window = series.iloc[start:end]

    if len(window) < 4 or window.isna().any():
        return None

    # Design 8: date-span validation.
    try:
        dates = pd.to_datetime(window.index, errors="raise")
        span_days = int((dates.max() - dates.min()).days)

        if span_days < _TTM_MIN_DAYS or span_days > _TTM_MAX_DAYS:
            logger.warning(
                "TTM date span of %d days (offset=%d) is outside the expected "
                "range [%d, %d]. The four selected quarters may not represent a "
                "full year. Returning None to avoid summing inconsistent data.",
                span_days, year_offset, _TTM_MIN_DAYS, _TTM_MAX_DAYS,
            )
            return None

    except Exception:
        # Column labels are not date-parseable — skip span check.
        pass

    return float(window.sum())