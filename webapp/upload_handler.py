"""
upload_handler.py
Handles the end-to-end processing of a single uploaded claims file.
"""

import hashlib
import io
import os
from datetime import datetime

import pandas as pd

from scripts.validate_claim_file import validate_claim_file
from scripts.process_medical_claims import process_medical_claims
from scripts.process_pharmacy_claims import process_pharmacy_claims
from scripts.append_to_master_dataset import append_medical_claims, append_pharmacy_claims
from webapp.onedrive_sync import upload_master

RAW_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "raw")

# In-memory set of processed file hashes (reset on server restart)
_processed_hashes: set = set()


def handle_upload(file_bytes: bytes, filename: str, tpa_source: str = "", report_month: str = "") -> dict:
    """
    Validate, process, and store a single uploaded claims file.

    Parameters
    ----------
    file_bytes : bytes
        Raw file content.
    filename : str
        Original filename (used for extension detection).
    tpa_source : str
        TPA / PBM label for provenance tracking.
    report_month : str
        Report month label (e.g. "2024-01").

    Returns
    -------
    dict
        Ingestion result with validation report and storage summary.
    """
    global _processed_hashes

    # Save raw copy
    os.makedirs(RAW_DIR, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    safe_name = f"{ts}_{filename}"
    raw_path = os.path.join(RAW_DIR, safe_name)
    with open(raw_path, "wb") as fh:
        fh.write(file_bytes)

    # Validate
    validation = validate_claim_file(
        source=file_bytes,
        filename=filename,
        existing_hashes=_processed_hashes,
    )

    if validation["validation_status"] != "passed":
        return {
            "status": "rejected",
            "filename": filename,
            "validation": validation,
        }

    # Register hash so future duplicates are detected
    _processed_hashes.add(hashlib.sha256(file_bytes).hexdigest())

    # Load normalized DataFrame
    ext = os.path.splitext(filename)[1].lower()
    buf = io.BytesIO(file_bytes)
    if ext == ".csv":
        df = pd.read_csv(buf, dtype=str)
    else:
        # Use the same smart sheet detection as validation
        from scripts.validate_claim_file import _best_excel_sheet
        df = _best_excel_sheet(buf)

    # Process based on detected type
    file_type = validation["detected_file_type"]
    if file_type == "medical":
        result = process_medical_claims(df, tpa_source=tpa_source, report_month=report_month)
        storage = append_medical_claims(result["data"])
        upload_master("medical")
        upload_master("members")
    else:
        result = process_pharmacy_claims(df, tpa_source=tpa_source, report_month=report_month)
        storage = append_pharmacy_claims(result["data"])
        upload_master("pharmacy")
        upload_master("members")

    return {
        "status": "accepted",
        "filename": filename,
        "file_type": file_type,
        "validation": validation,
        "processing": {
            "rows_in": result["rows_in"],
            "rows_out": result["rows_out"],
            "duplicates_removed": result["duplicates"],
            "phi_removed": result["phi_removed"],
        },
        "storage": storage,
    }
