"""
deduplicate_claims.py
Removes duplicate records from medical and pharmacy claims DataFrames.
"""

import pandas as pd


MEDICAL_UNIQUE_KEY = ["claim_number", "procedure_code", "service_date"]
PHARMACY_UNIQUE_KEY = ["rx_number", "fill_date", "ndc"]


def deduplicate_medical_claims(df: pd.DataFrame) -> tuple:
    """
    Remove duplicate medical claims using the composite key:
    claim_number + procedure_code + service_date.

    Returns
    -------
    (deduplicated_df, duplicates_removed_count)
    """
    key_cols = [c for c in MEDICAL_UNIQUE_KEY if c in df.columns]
    if not key_cols:
        return df, 0
    before = len(df)
    df = df.drop_duplicates(subset=key_cols, keep="first")
    return df, before - len(df)


def deduplicate_pharmacy_claims(df: pd.DataFrame) -> tuple:
    """
    Remove duplicate pharmacy claims using the composite key:
    rx_number + fill_date + ndc.

    Returns
    -------
    (deduplicated_df, duplicates_removed_count)
    """
    key_cols = [c for c in PHARMACY_UNIQUE_KEY if c in df.columns]
    if not key_cols:
        return df, 0
    before = len(df)
    df = df.drop_duplicates(subset=key_cols, keep="first")
    return df, before - len(df)
