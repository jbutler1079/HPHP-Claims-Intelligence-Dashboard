"""
process_pharmacy_claims.py
End-to-end processing pipeline for pharmacy claims data.
"""

import pandas as pd

from scripts.normalize_columns import normalize_and_clean
from scripts.calculate_metrics import calculate_pharmacy_metrics
from scripts.deduplicate_claims import deduplicate_pharmacy_claims

PHARMACY_SCHEMA = [
    "rx_number",
    "member_id",
    "fill_date",
    "ndc",
    "drug_name",
    "days_supply",
    "quantity",
    "ingredient_cost",
    "plan_paid",
    "member_paid",
    "employer_group",
    "age",
    "gender",
    "tpa_source",
    "report_month",
]


def process_pharmacy_claims(df: pd.DataFrame, tpa_source: str = "", report_month: str = "") -> dict:
    """
    Normalize, enrich, deduplicate, and return processed pharmacy claims.

    Parameters
    ----------
    df : pd.DataFrame
        Raw input DataFrame.
    tpa_source : str
        Label for the PBM/TPA sending this data (e.g. "TPA_B").
    report_month : str
        Reporting period label (e.g. "2024-01").

    Returns
    -------
    dict with keys:
        data          – processed DataFrame
        rows_in       – row count before deduplication
        rows_out      – row count after deduplication
        duplicates    – number of duplicates removed
        phi_removed   – list of PHI columns that were dropped
    """
    df, phi_removed = normalize_and_clean(df)

    if tpa_source and "tpa_source" not in df.columns:
        df["tpa_source"] = tpa_source
    if report_month and "report_month" not in df.columns:
        df["report_month"] = report_month

    # Coerce numeric types
    for col in ("ingredient_cost", "plan_paid", "member_paid", "days_supply", "quantity"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Coerce date
    if "fill_date" in df.columns:
        df["fill_date"] = pd.to_datetime(df["fill_date"], errors="coerce")

    df = calculate_pharmacy_metrics(df)

    rows_in = len(df)
    df, duplicates = deduplicate_pharmacy_claims(df)
    rows_out = len(df)

    ordered = [c for c in PHARMACY_SCHEMA if c in df.columns]
    extra = [c for c in df.columns if c not in ordered]
    df = df[ordered + extra]

    return {
        "data": df,
        "rows_in": rows_in,
        "rows_out": rows_out,
        "duplicates": duplicates,
        "phi_removed": phi_removed,
    }
