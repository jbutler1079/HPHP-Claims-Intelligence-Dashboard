"""
supabase_db.py
Persists processed claims DataFrames to Supabase (PostgreSQL).

Required Render environment variable
--------------------------------------
DATABASE_URL  – Supabase connection string, e.g.:
    postgresql://postgres:[YOUR-PASSWORD]@db.xxxx.supabase.co:5432/postgres

Tables are created automatically on first startup.
"""

import logging
import os
from datetime import date

import pandas as pd
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)

_DATABASE_URL = os.environ.get("DATABASE_URL", "")
_engine = None

MEDICAL_DEDUP  = ["claim_number", "procedure_code", "service_date"]
PHARMACY_DEDUP = ["rx_number", "fill_date", "ndc"]
MEMBERS_DEDUP  = ["member_id"]

_CREATE_MEDICAL = """
CREATE TABLE IF NOT EXISTS medical_claims (
    claim_number        TEXT,
    member_id           TEXT,
    service_date        TEXT,
    paid_date           TEXT,
    procedure_code      TEXT,
    diagnosis_code      TEXT,
    place_of_service    TEXT,
    billed_amount       DOUBLE PRECISION,
    allowed_amount      DOUBLE PRECISION,
    paid_amount         DOUBLE PRECISION,
    employer_group      TEXT,
    age                 DOUBLE PRECISION,
    gender              TEXT,
    tpa_source          TEXT,
    report_month        TEXT,
    service_to_paid_lag DOUBLE PRECISION,
    discount_percent    DOUBLE PRECISION,
    plan_paid_ratio     DOUBLE PRECISION,
    high_cost_flag      TEXT,
    very_high_cost_flag TEXT
);
"""

_CREATE_PHARMACY = """
CREATE TABLE IF NOT EXISTS pharmacy_claims (
    rx_number               TEXT,
    member_id               TEXT,
    fill_date               TEXT,
    ndc                     TEXT,
    drug_name               TEXT,
    days_supply             DOUBLE PRECISION,
    quantity                DOUBLE PRECISION,
    ingredient_cost         DOUBLE PRECISION,
    plan_paid               DOUBLE PRECISION,
    member_paid             DOUBLE PRECISION,
    employer_group          TEXT,
    age                     DOUBLE PRECISION,
    gender                  TEXT,
    tpa_source              TEXT,
    report_month            TEXT,
    total_rx_cost           DOUBLE PRECISION,
    member_cost_share_ratio DOUBLE PRECISION,
    high_cost_flag          TEXT,
    very_high_cost_flag     TEXT
);
"""

_CREATE_MEMBERS = """
CREATE TABLE IF NOT EXISTS members (
    member_id        TEXT,
    age              DOUBLE PRECISION,
    gender           TEXT,
    employer_group   TEXT,
    last_seen_date   TEXT,
    first_seen_date  TEXT
);
"""


def _is_configured() -> bool:
    return bool(_DATABASE_URL)


def _get_engine():
    global _engine
    if _engine is None:
        if not _DATABASE_URL:
            raise RuntimeError("DATABASE_URL environment variable is not set.")
        _engine = create_engine(
            _DATABASE_URL,
            pool_pre_ping=True,
            pool_size=2,
            max_overflow=3,
        )
    return _engine


def ensure_tables() -> None:
    """Create all three tables if they don't exist. Safe to call on every startup."""
    if not _is_configured():
        logger.info("DATABASE_URL not set — skipping Supabase table creation.")
        return
    try:
        engine = _get_engine()
        with engine.begin() as conn:
            conn.execute(text(_CREATE_MEDICAL))
            conn.execute(text(_CREATE_PHARMACY))
            conn.execute(text(_CREATE_MEMBERS))
        logger.info("Supabase: tables verified/created.")
    except Exception as exc:
        logger.error("Supabase: ensure_tables failed: %s", exc)


def _upsert(df: pd.DataFrame, table_name: str, dedup_keys: list) -> dict:
    """
    Insert only rows whose dedup key combination doesn't already exist.
    Rows that already exist are silently skipped (no overwrite).
    """
    if df is None or df.empty:
        return {"rows_inserted": 0, "rows_skipped": 0}

    engine = _get_engine()
    available_keys = [k for k in dedup_keys if k in df.columns]

    rows_to_insert = df.copy()

    if available_keys:
        try:
            with engine.connect() as conn:
                existing = pd.read_sql(
                    text(f"SELECT {', '.join(available_keys)} FROM {table_name}"),
                    conn,
                )
            existing_tuples = set(
                map(tuple, existing[available_keys].astype(str).values.tolist())
            )
            mask = ~df[available_keys].astype(str).apply(tuple, axis=1).isin(existing_tuples)
            rows_to_insert = df[mask].copy()
        except Exception:
            # Table is empty or first run — insert everything
            pass

    skipped = len(df) - len(rows_to_insert)

    if rows_to_insert.empty:
        return {"rows_inserted": 0, "rows_skipped": skipped}

    rows_to_insert.to_sql(
        table_name,
        engine,
        if_exists="append",
        index=False,
        method="multi",
        chunksize=500,
    )
    return {"rows_inserted": len(rows_to_insert), "rows_skipped": skipped}


def upsert_medical(df: pd.DataFrame) -> dict:
    if not _is_configured():
        return {"skipped": True, "reason": "DATABASE_URL not set"}
    try:
        return _upsert(df, "medical_claims", MEDICAL_DEDUP)
    except Exception as exc:
        logger.error("Supabase: upsert_medical failed: %s", exc)
        return {"error": str(exc)}


def upsert_pharmacy(df: pd.DataFrame) -> dict:
    if not _is_configured():
        return {"skipped": True, "reason": "DATABASE_URL not set"}
    try:
        return _upsert(df, "pharmacy_claims", PHARMACY_DEDUP)
    except Exception as exc:
        logger.error("Supabase: upsert_pharmacy failed: %s", exc)
        return {"error": str(exc)}


def upsert_members(claims_df: pd.DataFrame) -> dict:
    """Extract member dimension rows from any claims DataFrame and upsert."""
    if not _is_configured():
        return {"skipped": True, "reason": "DATABASE_URL not set"}
    try:
        member_cols = [
            c for c in ["member_id", "age", "gender", "employer_group"]
            if c in claims_df.columns
        ]
        if "member_id" not in member_cols:
            return {"skipped": True, "reason": "no member_id column"}

        today = str(date.today())
        members_df = claims_df[member_cols].drop_duplicates(subset=["member_id"]).copy()
        members_df["last_seen_date"] = today

        # Preserve first_seen_date for existing members
        engine = _get_engine()
        try:
            with engine.connect() as conn:
                existing_dates = pd.read_sql(
                    text("SELECT member_id, first_seen_date FROM members"),
                    conn,
                )
            existing_map = dict(
                zip(existing_dates["member_id"], existing_dates["first_seen_date"])
            )
        except Exception:
            existing_map = {}

        members_df["first_seen_date"] = members_df["member_id"].apply(
            lambda mid: existing_map.get(mid, today)
        )

        # Delete stale member rows so we can re-insert with updated data
        if existing_map:
            ids = members_df["member_id"].dropna().tolist()
            if ids:
                placeholders = ", ".join(f"'{m}'" for m in ids)
                with engine.begin() as conn:
                    conn.execute(
                        text(f"DELETE FROM members WHERE member_id IN ({placeholders})")
                    )

        members_df.to_sql(
            "members", engine, if_exists="append", index=False,
            method="multi", chunksize=500,
        )
        return {"members_upserted": len(members_df)}
    except Exception as exc:
        logger.error("Supabase: upsert_members failed: %s", exc)
        return {"error": str(exc)}
