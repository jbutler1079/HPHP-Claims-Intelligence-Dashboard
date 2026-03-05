"""
process_medical_claims.py
End-to-end processing pipeline for medical claims data.
"""

import pandas as pd

from scripts.normalize_columns import normalize_and_clean
from scripts.calculate_metrics import calculate_medical_metrics
from scripts.deduplicate_claims import deduplicate_medical_claims

MEDICAL_SCHEMA = [
    "claim_number",
    "member_id",
    "service_date",
    "paid_date",
    "procedure_code",
    "diagnosis_code",
    "place_of_service",
    "billed_amount",
    "allowed_amount",
    "paid_amount",
    "employer_group",
    "age",
    "gender",
    "tpa_source",
    "report_month",
]


def process_medical_claims(df: pd.DataFrame, tpa_source: str = "", report_month: str = "") -> dict:
    """
    Normalize, enrich, deduplicate, and return processed medical claims.

    Parameters
    ----------
    df : pd.DataFrame
        Raw input DataFrame (as loaded from the uploaded file).
    tpa_source : str
        Label for the TPA sending this data (e.g. "TPA_A").
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

    # Inject metadata columns if supplied
    if tpa_source and "tpa_source" not in df.columns:
        df["tpa_source"] = tpa_source
    if report_month and "report_month" not in df.columns:
        df["report_month"] = report_month

    # Coerce numeric types (strip currency formatting first: $, commas, parens)
    for col in ("billed_amount", "allowed_amount", "paid_amount"):
        if col in df.columns:
            cleaned = (
                df[col].astype(str)
                .str.replace(r"[$,\s]", "", regex=True)
                .str.replace(r"^\((.+)\)$", r"-\1", regex=True)
            )
            df[col] = pd.to_numeric(cleaned, errors="coerce")

    # Coerce date types
    for col in ("service_date", "paid_date"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    df = calculate_medical_metrics(df)

    rows_in = len(df)
    df, duplicates = deduplicate_medical_claims(df)
    rows_out = len(df)

    # Reorder to schema (only present columns)
    ordered = [c for c in MEDICAL_SCHEMA if c in df.columns]
    extra = [c for c in df.columns if c not in ordered]
    df = df[ordered + extra]

    return {
        "data": df,
        "rows_in": rows_in,
        "rows_out": rows_out,
        "duplicates": duplicates,
        "phi_removed": phi_removed,
    }
