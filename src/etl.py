"""
ETL Pipeline — Multi-Source B2B Marketplace Data
=================================================
Combines IndiaMART + TradeIndia data and transforms into analytics-ready output:

  Extract  : Load raw CSV from /data/ (indiamart_raw.csv, tradeindia_raw.csv)
  Transform: Validate fields, normalize prices, standardise locations,
             smart deduplication, derive new columns
  Load     : Write combined CSV + Parquet to /data/clean/

Run:
    python src/etl.py
"""

import pandas as pd
import numpy as np
import os
import re
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

RAW_DIR   = os.path.join(os.path.dirname(__file__), "..", "data")
CLEAN_DIR = os.path.join(RAW_DIR, "clean")

# ── State name normalisation map ──────────────────────────────────────────────
STATE_MAP = {
    "mumbai": "Maharashtra", "pune": "Maharashtra", "nagpur": "Maharashtra",
    "delhi": "Delhi", "new delhi": "Delhi", "noida": "Uttar Pradesh", "gurgaon": "Haryana",
    "bengaluru": "Karnataka", "bangalore": "Karnataka", "mysuru": "Karnataka",
    "chennai": "Tamil Nadu", "coimbatore": "Tamil Nadu", "madurai": "Tamil Nadu",
    "hyderabad": "Telangana", "secunderabad": "Telangana",
    "ahmedabad": "Gujarat", "surat": "Gujarat", "vadodara": "Gujarat",
    "kolkata": "West Bengal", "howrah": "West Bengal",
    "jaipur": "Rajasthan", "jodhpur": "Rajasthan",
    "ludhiana": "Punjab", "amritsar": "Punjab",
    "bhopal": "Madhya Pradesh", "indore": "Madhya Pradesh",
    "patna": "Bihar", "lucknow": "Uttar Pradesh", "kanpur": "Uttar Pradesh",
    "kochi": "Kerala", "thiruvananthapuram": "Kerala",
}


def extract(filepath: str) -> pd.DataFrame:
    """Load raw data file (CSV or JSON)."""
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".csv":
        df = pd.read_csv(filepath)
    elif ext == ".json":
        df = pd.read_json(filepath)
    else:
        raise ValueError(f"Unsupported file type: {ext}")
    logger.info(f"📥 Extracted {len(df)} rows from {os.path.basename(filepath)}")
    return df


def validate(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Run field-level validations and return DQ report."""
    dq = {
        "total_records":    len(df),
        "timestamp":        datetime.utcnow().isoformat(),
        "field_completeness": {},
        "duplicate_count":  0,
        "invalid_prices":   0,
        "invalid_ratings":  0,
    }

    required_fields = ["product_name", "supplier_name", "location", "category"]
    for field in required_fields:
        if field in df.columns:
            completeness = df[field].notna().mean() * 100
            dq["field_completeness"][field] = round(completeness, 1)

    # Drop rows with no product name (required field gate)
    before = len(df)
    df = df.dropna(subset=["product_name"])
    dropped = before - len(df)
    if dropped:
        logger.warning(f"⚠️  Dropped {dropped} rows missing product_name")

    # Duplicate check
    dq["duplicate_count"] = df.duplicated(subset=["product_name", "supplier_name", "location"]).sum()

    # Price sanity
    if "price_min" in df.columns:
        dq["invalid_prices"] = int((df["price_min"] < 0).sum())

    # Rating sanity
    if "rating" in df.columns:
        dq["invalid_ratings"] = int(((df["rating"] < 0) | (df["rating"] > 5)).sum())

    overall = round(
        df[[c for c in required_fields if c in df.columns]].notna().mean().mean() * 100, 1
    )
    dq["overall_completeness"] = overall
    logger.info(f"📋 DQ: {overall}% completeness, {dq['duplicate_count']} duplicates")

    return df, dq


def clean_location(loc: str) -> tuple[str, str]:
    """Parse 'Mumbai, Maharashtra' into (city, state)."""
    if not loc or loc == "Unknown":
        return "Unknown", "Unknown"

    loc = str(loc).strip()
    parts = [p.strip() for p in loc.split(",")]
    city  = parts[0].title() if parts else "Unknown"
    state = parts[1].title() if len(parts) > 1 else STATE_MAP.get(city.lower(), "Unknown")

    if state == "Unknown":
        state = STATE_MAP.get(city.lower(), "Unknown")

    return city, state


def normalize_price(row: pd.Series) -> pd.Series:
    """Clip outliers, fill missing price_max from price_min."""
    if pd.notna(row.get("price_min")) and pd.isna(row.get("price_max")):
        row["price_max"] = row["price_min"]
    if pd.notna(row.get("price_min")) and pd.notna(row.get("price_max")):
        row["price_mid"] = (row["price_min"] + row["price_max"]) / 2
        row["price_range_flag"] = "range" if row["price_min"] != row["price_max"] else "fixed"
    else:
        row["price_mid"] = None
        row["price_range_flag"] = "unknown"
    return row


def transform(df: pd.DataFrame) -> pd.DataFrame:
    """Apply all transformations."""

    # ── 1. Deduplicate ────────────────────────────────────────────────────────
    before = len(df)
    df = df.drop_duplicates(subset=["product_name", "supplier_name", "location"])
    logger.info(f"🔄 Deduplication: {before} → {len(df)} records")

    # ── 2. Location parsing ───────────────────────────────────────────────────
    loc_parsed = df["location"].fillna("Unknown").apply(clean_location)
    df["city"]  = loc_parsed.apply(lambda x: x[0])
    df["state"] = loc_parsed.apply(lambda x: x[1])

    # ── 3. Price normalisation ────────────────────────────────────────────────
    df = df.apply(normalize_price, axis=1)
    if "price_min" in df.columns:
        # Clip extreme outliers (> 99th percentile)
        p99 = df["price_min"].quantile(0.99)
        df.loc[df["price_min"] > p99, ["price_min", "price_max", "price_mid"]] = np.nan

    # ── 4. Rating normalisation ───────────────────────────────────────────────
    if "rating" in df.columns:
        df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
        df.loc[(df["rating"] < 0) | (df["rating"] > 5), "rating"] = np.nan

    # ── 5. Derived columns ────────────────────────────────────────────────────
    df["product_name_clean"] = (
        df["product_name"]
        .str.strip()
        .str.title()
        .str.replace(r"\s+", " ", regex=True)
    )

    # Keyword extraction from product name
    df["keywords"] = df["product_name_clean"].apply(
        lambda x: " ".join(
            w for w in str(x).lower().split()
            if len(w) > 3 and w not in {"with", "this", "that", "from", "and", "for"}
        )
    )

    df["price_bucket"] = pd.cut(
        df.get("price_mid", pd.Series([np.nan]*len(df))),
        bins=[0, 100, 500, 1000, 5000, 10000, float("inf")],
        labels=["<₹100", "₹100-500", "₹500-1K", "₹1K-5K", "₹5K-10K", ">₹10K"],
        right=False
    )

    df["verified"] = df.get("verified", pd.Series([False]*len(df))).fillna(False).astype(bool)

    df["scraped_date"] = pd.to_datetime(df.get("scraped_at", pd.Timestamp.now())).dt.date

    # ── 6. Column order ───────────────────────────────────────────────────────
    ordered_cols = [
        "product_name_clean", "supplier_name", "city", "state", "category",
        "price_min", "price_max", "price_mid", "price_unit", "price_bucket", "price_range_flag",
        "currency", "rating", "moq", "verified", "keywords", "product_url", "scraped_date"
    ]
    available = [c for c in ordered_cols if c in df.columns]
    df = df[available]

    logger.info(f"✅ Transform complete: {len(df)} clean records, {len(df.columns)} columns")
    return df


def load(df: pd.DataFrame, dq: dict):
    """Write clean data and DQ report."""
    os.makedirs(CLEAN_DIR, exist_ok=True)

    csv_path     = os.path.join(CLEAN_DIR, "indiamart_clean.csv")
    parquet_path = os.path.join(CLEAN_DIR, "indiamart_clean.parquet")
    dq_path      = os.path.join(CLEAN_DIR, "data_quality_report.json")

    df.to_csv(csv_path, index=False)
    df.to_parquet(parquet_path, index=False)

    import json
    with open(dq_path, "w") as f:
        json.dump(dq, f, indent=2, default=str)

    logger.info(f"💾 CSV     → {csv_path}")
    logger.info(f"💾 Parquet → {parquet_path}")
    logger.info(f"📋 DQ      → {dq_path}")


def run_etl(raw_filepath: str = None):
    """Full ETL pipeline."""
    if raw_filepath is None:
        raw_filepath = os.path.join(RAW_DIR, "indiamart_raw.csv")

    if not os.path.exists(raw_filepath):
        # Use sample data if scraper hasn't run yet
        raw_filepath = os.path.join(RAW_DIR, "indiamart_sample.csv")
        logger.info(f"Raw file not found — using sample data: {raw_filepath}")

    logger.info("🚀 Starting ETL pipeline")
    df_raw           = extract(raw_filepath)
    df_valid, dq     = validate(df_raw)
    df_clean         = transform(df_valid)
    load(df_clean, dq)
    logger.info(f"✅ ETL complete — {len(df_clean)} analytics-ready records")
    return df_clean


if __name__ == "__main__":
    df = run_etl()
    print("\nSample output:")
    print(df.head(3).to_string())
    print(f"\nShape: {df.shape}")
    print(f"\nColumns: {list(df.columns)}")
