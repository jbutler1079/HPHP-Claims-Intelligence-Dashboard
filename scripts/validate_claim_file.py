"""
validate_claim_file.py
Validates an uploaded claims file before it enters the processing pipeline.
"""

import hashlib
import io
import os
from datetime import datetime
from typing import Union

import pandas as pd

from config.column_mapping import (
    COLUMN_MAPPING,
    PHI_FIELDS,
    MEDICAL_INDICATORS,
    PHARMACY_INDICATORS,
    REQUIRED_MEDICAL_COLUMNS,
    REQUIRED_PHARMACY_COLUMNS,
)


def _load_dataframe(file_path: str) -> pd.DataFrame:
    """Load a CSV or Excel file into a DataFrame."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".csv":
        return pd.read_csv(file_path, dtype=str)
    if ext in (".xlsx", ".xls"):
        return pd.read_excel(file_path, dtype=str)
    raise ValueError(f"Unsupported file type: {ext!r}")


def _load_dataframe_from_bytes(data: bytes, filename: str) -> pd.DataFrame:
    """Load a CSV or Excel file from raw bytes."""
    ext = os.path.splitext(filename)[1].lower()
    buf = io.BytesIO(data)
    if ext == ".csv":
        return pd.read_csv(buf, dtype=str)
    if ext in (".xlsx", ".xls"):
        return pd.read_excel(buf, dtype=str)
    raise ValueError(f"Unsupported file type: {ext!r}")


def _normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Apply the column mapping to normalize column headers."""
    return df.rename(columns=COLUMN_MAPPING)


def _detect_file_type(columns: list) -> str:
    """Detect whether the file contains medical or pharmacy claims."""
    col_set = set(c.lower() for c in columns)
    medical_hits = sum(1 for ind in MEDICAL_INDICATORS if ind in col_set)
    pharmacy_hits = sum(1 for ind in PHARMACY_INDICATORS if ind in col_set)
    if medical_hits >= pharmacy_hits:
        return "medical"
    return "pharmacy"


def _detect_phi_columns(columns: list) -> list:
    """Return any columns that match known PHI field names."""
    phi_lower = {f.lower() for f in PHI_FIELDS}
    return [c for c in columns if c.lower() in phi_lower]


def _validate_dates(df: pd.DataFrame, date_columns: list) -> list:
    """Return list of columns where date parsing fails for any row."""
    invalid = []
    for col in date_columns:
        if col not in df.columns:
            continue
        parsed = pd.to_datetime(df[col], errors="coerce")
        if parsed.isna().any():
            invalid.append(col)
    return invalid


def _validate_numerics(df: pd.DataFrame, numeric_columns: list) -> list:
    """Return list of columns where numeric conversion fails for any row."""
    invalid = []
    for col in numeric_columns:
        if col not in df.columns:
            continue
        converted = pd.to_numeric(df[col], errors="coerce")
        if converted.isna().any():
            invalid.append(col)
    return invalid


def validate_claim_file(
    source: Union[str, bytes],
    filename: str = "",
    existing_hashes: set = None,
) -> dict:
    """
    Validate a claims file.

    Parameters
    ----------
    source : str or bytes
        Either a filesystem path (str) or the raw file bytes.
    filename : str
        Original filename – used for extension detection when *source* is bytes,
        and always included in the report.
    existing_hashes : set, optional
        Set of previously seen file hashes used for duplicate‑file detection.

    Returns
    -------
    dict
        Validation report with keys:
        file_name, rows_processed, missing_columns, invalid_fields,
        detected_file_type, validation_status, phi_columns_removed
    """
    if existing_hashes is None:
        existing_hashes = set()

    report = {
        "file_name": filename or (source if isinstance(source, str) else ""),
        "rows_processed": 0,
        "missing_columns": [],
        "invalid_fields": [],
        "detected_file_type": "unknown",
        "validation_status": "failed",
        "phi_columns_removed": [],
    }

    # File-type check
    fname = filename or (source if isinstance(source, str) else "")
    ext = os.path.splitext(fname)[1].lower()
    if ext not in (".csv", ".xlsx", ".xls"):
        report["invalid_fields"].append(f"unsupported_file_extension:{ext}")
        return report

    # Load data
    try:
        if isinstance(source, bytes):
            df = _load_dataframe_from_bytes(source, fname)
        else:
            df = _load_dataframe(source)
    except Exception as exc:
        report["invalid_fields"].append(f"load_error:{exc}")
        return report

    report["rows_processed"] = len(df)

    # Duplicate file detection (hash of raw content)
    if isinstance(source, bytes):
        file_hash = hashlib.sha256(source).hexdigest()
    else:
        with open(source, "rb") as fh:
            file_hash = hashlib.sha256(fh.read()).hexdigest()

    if file_hash in existing_hashes:
        report["invalid_fields"].append("duplicate_file_detected")
        return report

    # PHI removal
    phi_detected = _detect_phi_columns(list(df.columns))
    if phi_detected:
        report["phi_columns_removed"] = phi_detected
        df = df.drop(columns=phi_detected, errors="ignore")

    # Column normalization
    df = _normalize_column_names(df)

    # Detect file type
    report["detected_file_type"] = _detect_file_type(list(df.columns))

    # Required columns
    if report["detected_file_type"] == "medical":
        required = REQUIRED_MEDICAL_COLUMNS
        date_cols = ["service_date", "paid_date"]
        numeric_cols = ["billed_amount", "allowed_amount", "paid_amount"]
    else:
        required = REQUIRED_PHARMACY_COLUMNS
        date_cols = ["fill_date"]
        numeric_cols = ["ingredient_cost", "plan_paid", "member_paid"]

    missing = [c for c in required if c not in df.columns]
    report["missing_columns"] = missing

    # Date validation
    invalid_dates = _validate_dates(df, date_cols)
    report["invalid_fields"].extend([f"invalid_date:{c}" for c in invalid_dates])

    # Numeric validation
    invalid_nums = _validate_numerics(df, numeric_cols)
    report["invalid_fields"].extend([f"invalid_numeric:{c}" for c in invalid_nums])

    # Final status
    if not missing and not report["invalid_fields"]:
        report["validation_status"] = "passed"
    else:
        report["validation_status"] = "failed"

    return report
