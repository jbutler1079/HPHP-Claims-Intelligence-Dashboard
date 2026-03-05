"""
append_to_master_dataset.py
Appends validated, processed records to the cumulative master CSV datasets
and maintains the members dimension table.
"""

import os
from datetime import date

import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")

MEDICAL_MASTER = os.path.join(PROCESSED_DIR, "medical_claims_master.csv")
PHARMACY_MASTER = os.path.join(PROCESSED_DIR, "pharmacy_claims_master.csv")
MEMBERS_MASTER = os.path.join(PROCESSED_DIR, "members_master.csv")

MEDICAL_DEDUP_KEY = ["claim_number", "procedure_code", "service_date"]
PHARMACY_DEDUP_KEY = ["rx_number", "fill_date", "ndc"]


def _append_to_csv(new_df: pd.DataFrame, master_path: str, dedup_keys: list) -> dict:
    """
    Load the existing master CSV (if any), append *new_df*, deduplicate, and save.

    Returns a summary dict.
    """
    if os.path.exists(master_path):
        existing = pd.read_csv(master_path, dtype=str, low_memory=False)
    else:
        existing = pd.DataFrame()

    combined = pd.concat([existing, new_df.astype(str)], ignore_index=True)

    available_keys = [k for k in dedup_keys if k in combined.columns]
    if available_keys:
        combined = combined.drop_duplicates(subset=available_keys, keep="last")

    combined.to_csv(master_path, index=False)

    return {
        "records_before": len(existing),
        "records_added": len(new_df),
        "records_after": len(combined),
    }


def update_members_master(df: pd.DataFrame) -> dict:
    """
    Upsert member dimension records from any claims DataFrame that contains
    member_id, age, gender, and employer_group columns.
    """
    needed = {"member_id", "age", "gender", "employer_group"}
    present = needed.intersection(set(df.columns))
    if "member_id" not in present:
        return {"skipped": True, "reason": "no member_id column"}

    today = str(date.today())
    member_cols = list(present)
    members = df[member_cols].drop_duplicates(subset=["member_id"]).copy()
    members["last_seen_date"] = today

    if os.path.exists(MEMBERS_MASTER):
        existing = pd.read_csv(MEMBERS_MASTER, dtype=str, low_memory=False)
    else:
        existing = pd.DataFrame()

    if existing.empty:
        members["first_seen_date"] = today
        members.to_csv(MEMBERS_MASTER, index=False)
        return {"members_upserted": len(members)}

    # Merge to preserve first_seen_date
    merged = pd.concat([existing, members], ignore_index=True)

    # Keep first occurrence for first_seen_date, last for everything else
    first_seen = (
        merged.dropna(subset=["member_id"])
        .sort_values("first_seen_date", na_position="last")
        .drop_duplicates(subset=["member_id"], keep="first")[["member_id", "first_seen_date"]]
    )

    latest = (
        merged.drop_duplicates(subset=["member_id"], keep="last")
        .drop(columns=["first_seen_date"], errors="ignore")
    )

    result = latest.merge(first_seen, on="member_id", how="left")
    if "first_seen_date" not in result.columns:
        result["first_seen_date"] = today

    result.to_csv(MEMBERS_MASTER, index=False)
    return {"members_upserted": len(result)}


def append_medical_claims(df: pd.DataFrame) -> dict:
    """Append processed medical claims to the master dataset."""
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    result = _append_to_csv(df, MEDICAL_MASTER, MEDICAL_DEDUP_KEY)
    member_result = update_members_master(df)
    result["members"] = member_result
    return result


def append_pharmacy_claims(df: pd.DataFrame) -> dict:
    """Append processed pharmacy claims to the master dataset."""
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    result = _append_to_csv(df, PHARMACY_MASTER, PHARMACY_DEDUP_KEY)
    member_result = update_members_master(df)
    result["members"] = member_result
    return result
