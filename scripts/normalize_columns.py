"""
normalize_columns.py
Renames raw TPA/PBM column headers to the HPHP standard schema and removes PHI.
"""

import pandas as pd

from config.column_mapping import COLUMN_MAPPING, PHI_FIELDS


def remove_phi_columns(df: pd.DataFrame) -> tuple:
    """
    Drop any columns that match known PHI field names.

    Returns
    -------
    (cleaned_df, removed_columns)
    """
    phi_lower = {f.lower() for f in PHI_FIELDS}
    to_drop = [c for c in df.columns if c.lower() in phi_lower]
    return df.drop(columns=to_drop, errors="ignore"), to_drop


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply the COLUMN_MAPPING to standardize column names (case-insensitive).
    Any columns not found in the mapping are left unchanged.
    """
    ci_map = {k.strip().lower(): v for k, v in COLUMN_MAPPING.items()}
    target_names = set(COLUMN_MAPPING.values())
    renamed = {}
    for col in df.columns:
        key = col.strip().lower()
        if key in ci_map:
            renamed[col] = ci_map[key]
        elif key in target_names:
            renamed[col] = key
    return df.rename(columns=renamed)


def normalize_and_clean(df: pd.DataFrame) -> tuple:
    """
    Remove PHI fields and normalize column names in one pass.

    Returns
    -------
    (cleaned_df, removed_phi_columns)
    """
    df, removed = remove_phi_columns(df)
    df = normalize_columns(df)
    return df, removed
