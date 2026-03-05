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
    Apply the COLUMN_MAPPING to standardize column names.
    Any columns not found in the mapping are left unchanged.
    """
    return df.rename(columns=COLUMN_MAPPING)


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
