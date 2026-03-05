"""
calculate_metrics.py
Computes derived analytics metrics for normalized claims DataFrames.
"""

import pandas as pd


def calculate_medical_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Add calculated columns to a medical claims DataFrame."""
    df = df.copy()

    # Ensure numeric types
    for col in ("billed_amount", "allowed_amount", "paid_amount"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # service_to_paid_lag (days)
    if "service_date" in df.columns and "paid_date" in df.columns:
        df["service_date"] = pd.to_datetime(df["service_date"], errors="coerce")
        df["paid_date"] = pd.to_datetime(df["paid_date"], errors="coerce")
        df["service_to_paid_lag"] = (df["paid_date"] - df["service_date"]).dt.days

    # discount_percent = (billed - allowed) / billed
    if "billed_amount" in df.columns and "allowed_amount" in df.columns:
        billed = df["billed_amount"]
        allowed = df["allowed_amount"]
        df["discount_percent"] = (billed - allowed) / billed.replace(0, float("nan"))

    # plan_paid_ratio = paid / allowed
    if "paid_amount" in df.columns and "allowed_amount" in df.columns:
        df["plan_paid_ratio"] = df["paid_amount"] / df["allowed_amount"].replace(
            0, float("nan")
        )

    # Cost flags
    if "paid_amount" in df.columns:
        df["high_cost_flag"] = df["paid_amount"] > 10_000
        df["very_high_cost_flag"] = df["paid_amount"] > 50_000

    return df


def calculate_pharmacy_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Add calculated columns to a pharmacy claims DataFrame."""
    df = df.copy()

    for col in ("ingredient_cost", "plan_paid", "member_paid"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # total_rx_cost = ingredient_cost + member_paid (when available)
    if "ingredient_cost" in df.columns and "member_paid" in df.columns:
        df["total_rx_cost"] = df["ingredient_cost"].fillna(0) + df[
            "member_paid"
        ].fillna(0)

    # member_cost_share_ratio = member_paid / total_rx_cost
    if "member_paid" in df.columns and "total_rx_cost" in df.columns:
        df["member_cost_share_ratio"] = df["member_paid"] / df[
            "total_rx_cost"
        ].replace(0, float("nan"))

    # High cost flags (plan_paid thresholds)
    if "plan_paid" in df.columns:
        df["high_cost_flag"] = df["plan_paid"] > 10_000
        df["very_high_cost_flag"] = df["plan_paid"] > 50_000

    return df
