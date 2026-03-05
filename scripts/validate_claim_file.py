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


def _best_excel_sheet(buf, engine=None) -> pd.DataFrame:
    """Read the Excel sheet with the most columns (skips empty/summary tabs)."""
    xls = pd.ExcelFile(buf, engine=engine)
    best_df = pd.DataFrame()
    for name in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=name, dtype=str)
        if len(df.columns) > len(best_df.columns):
            best_df = df
    return best_df


def _load_dataframe(file_path: str) -> pd.DataFrame:
    """Load a CSV or Excel file into a DataFrame."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".csv":
        return pd.read_csv(file_path, dtype=str)
    if ext in (".xlsx", ".xls"):
        return _best_excel_sheet(file_path)
    raise ValueError(f"Unsupported file type: {ext!r}")


def _load_dataframe_from_bytes(data: bytes, filename: str) -> pd.DataFrame:
    """Load a CSV or Excel file from raw bytes."""
    ext = os.path.splitext(filename)[1].lower()
    buf = io.BytesIO(data)
    if ext == ".csv":
        return pd.read_csv(buf, dtype=str)
    if ext in (".xlsx", ".xls"):
        return _best_excel_sheet(buf)
    raise ValueError(f"Unsupported file type: {ext!r}")


def _normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Apply the column mapping to normalize column headers (case-insensitive)."""
    # Build a case-insensitive lookup: stripped/lowered raw name -> normalized name
    ci_map = {k.strip().lower(): v for k, v in COLUMN_MAPPING.items()}
    # Also accept columns that are already in normalized form (e.g. "member_id")
    target_names = set(COLUMN_MAPPING.values())
    renamed = {}
    for col in df.columns:
        key = col.strip().lower()
        if key in ci_map:
            renamed[col] = ci_map[key]
        elif key in target_names:
            renamed[col] = key  # already normalized, just fix casing
    return df.rename(columns=renamed)


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
    """Return columns with non-empty date values that fail parsing."""
    invalid = []
    for col in date_columns:
        if col not in df.columns:
            continue
        # Empty strings/nulls are treated as missing, not invalid values.
        raw = df[col]
        present_mask = raw.notna() & (raw.astype(str).str.strip() != "")
        if not present_mask.any():
            continue
        parsed = pd.to_datetime(raw[present_mask], errors="coerce")
        if parsed.isna().any():
            invalid.append(col)
    return invalid


def _validate_numerics(df: pd.DataFrame, numeric_columns: list) -> list:
    """Return columns with non-empty numeric values that fail conversion.

    Accepts currency-formatted values (e.g. ``$1,234.56``, ``(500.00)``) by
    stripping ``$``, commas, and parenthetical negatives before conversion.
    """
    invalid = []
    for col in numeric_columns:
        if col not in df.columns:
            continue
        # Empty strings/nulls are treated as missing, not invalid values.
        raw = df[col]
        present_mask = raw.notna() & (raw.astype(str).str.strip() != "")
        if not present_mask.any():
            continue
        # Normalise common currency formatting before numeric coercion.
        cleaned = (
            raw[present_mask]
            .astype(str)
            .str.replace(r"[$,\s]", "", regex=True)         # strip $, commas, spaces
            .str.replace(r"^\((.+)\)$", r"-\1", regex=True) # (123.45) -> -123.45
        )
        converted = pd.to_numeric(cleaned, errors="coerce")
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
