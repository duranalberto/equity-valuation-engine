import re
import pandas as pd
from typing import Optional, Iterable, Any, Union, List



def normalize_label(label: Any) -> str:
    """
    Normalizes arbitrary strings into stable match keys.

    Rules applied:
    - Lowercase
    - Replace any non-alphanumeric with underscore
    - Collapse multiple underscores
    - Strip leading/trailing underscores
    """
    s = re.sub(r"[^a-zA-Z0-9]+", "_", str(label).lower())
    return re.sub(r"_+", "_", s).strip("_")


def normalize_df_index(df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns a copy of df where the index is normalized using normalize_label.
    Does not mutate df in place.

    
    """
    if df is None or df.empty:
        return df

    new_df = df.copy()
    try:
        new_df.index = [normalize_label(i) for i in new_df.index]
    except Exception:
        pass
    return new_df



def _find_matching_index(df: pd.DataFrame, normalized_candidates: Iterable[str]) -> Optional[str]:
    """
    Internal: Strict match only:
    normalized_candidate == normalized_df_index_label
    """
    if df is None or df.empty:
        return None

    index_norm_map = {normalize_label(idx): idx for idx in df.index}

    for cand in normalized_candidates:
        nc = normalize_label(cand)
        if nc in index_norm_map:
            return index_norm_map[nc]

    return None


def _find_matching_column(df: pd.DataFrame, normalized_candidates: Iterable[str]) -> Optional[str]:
    """
    Internal: Strict match only:
    normalized_candidate == normalized_df_column_label
    """
    if df is None or df.empty:
        return None

    col_norm_map = {normalize_label(c): c for c in df.columns}

    for cand in normalized_candidates:
        nc = normalize_label(cand)
        if nc in col_norm_map:
            return col_norm_map[nc]

    return None


def _order_df_columns_by_date(df: pd.DataFrame, descending: bool = True) -> pd.DataFrame:
    """
    Internal: Reorder columns by date semantics.
    """
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
    new_cols = [c for c, _ in sortable_sorted] + unsortable

    return df.reindex(columns=new_cols)


def _extract_numeric_row(df: pd.DataFrame, idx: Any) -> pd.Series:
    """
    Internal: Extract a numeric row and chronologically sort its labels (if dates).
    Assumes df index is already normalized.
    """
    if df is None or df.empty or idx not in df.index:
        return pd.Series(dtype=float)

    row = pd.to_numeric(df.loc[idx], errors="coerce").dropna()

    if row.empty:
        return row

    try:
        dt_index = pd.to_datetime(row.index, errors="raise")
        row = row.loc[dt_index.sort_values().index]
        return row
    except Exception:
        pass
    
    try:
        return row.sort_index()
    except Exception:
        return row


def extract_from_dataframe(
    df: pd.DataFrame,
    candidates: list[str],
    from_index: bool = False,
    as_list: bool = False
) -> Optional[Union[pd.Series, list]]:
    """
    Strict deterministic extractor for a row (from_index=True) or a column (from_index=False).

    It normalizes the labels internally before matching.
    """
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


def _flatten_and_clean_numeric(values: list[Any]) -> list[float]:
    """
    Internal: Converts a list of potentially mixed types/structures into a flat list of floats, dropping NaNs.
    """
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
    numeric_candidates: list[str]
) -> Optional[list[float]]:
    """
    Extracts the first strictly matched or available numeric column, sorted by date_col.

    
    """
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


def _find_row_index(df: pd.DataFrame, labels: list[str]) -> Optional[Any]:
    """
    Internal: Strict row matcher on a normalized DataFrame index.
    """
    return _find_matching_index(df, labels)


def _extract_ordered_row(row: pd.Series, descending: bool = True) -> pd.Series:
    """
    Internal: Returns a single row Series sorted chronologically by column labels.
    """
    if row is None or row.empty:
        return row

    row_df = pd.DataFrame([row])
    row_df = _order_df_columns_by_date(row_df, descending=descending)
    return row_df.iloc[0]


def get_ordered_numeric_series(
    df: pd.DataFrame, 
    labels: Union[List[str], str]
) -> Optional[pd.Series]:
    """
    Normalizes DataFrame index, finds the row matching the labels,
    and returns the numeric values of that row ordered by date (descending).
    
    Parameters:
        df: The financial statement DataFrame (e.g., income statement).
        labels: A single label string or a list of label candidates for the row.
        
    Returns:
        A pd.Series of numeric values ordered descending by date, or None if not found/empty.
    """
    if df.empty:
        return None
    
    label_list = [labels] if isinstance(labels, str) else labels

    normalized_df = normalize_df_index(df)

    idx = _find_row_index(normalized_df, label_list)
    if idx is None or idx not in normalized_df.index:
        return None
    
    row = _extract_numeric_row(normalized_df, idx)
    if row.empty or row.isna().all():
        return None
    
    ordered = _extract_ordered_row(row, descending=True)
    numeric = pd.to_numeric(ordered, errors="coerce").dropna()
    
    return numeric if not numeric.empty else None


def calculate_ttm_from_series(
    series: pd.Series, 
    year_offset: int
) -> Optional[float]:
    """
    Calculates the TTM sum (sum of 4 latest quarters) from an ordered quarterly 
    numeric series, accounting for a year offset.
    
    The series must be ordered descending by date (most recent first).
    
    Parameters:
        series: A pd.Series of quarterly numeric values, ordered descending by date.
        year_offset: The offset (0 for latest TTM, 1 for previous TTM, etc.).
        
    Returns:
        The TTM sum as a float, or None if insufficient data is available.
    """

    needed = (year_offset + 1) * 4 
    if len(series) < needed:
        return None

    start = year_offset * 4
    end = start + 4
    window = series.iloc[start:end]

    if len(window) < 4 or window.isna().any():
        return None

    return float(window.sum())