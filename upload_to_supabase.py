"""
Upload combined_raw.csv to Supabase via REST API.
Run: python upload_to_supabase.py
"""

import pandas as pd
import requests
import re
import math
import json

SUPABASE_URL = "https://ayioshdnrdbevujphscb.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImF5aW9zaGRucmRiZXZ1anBoc2NiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODE2MDM2MzMsImV4cCI6MjA5NzE3OTYzM30.EULHrH2MYDuNh3U59LIdoWlspl0soUsJHeq0eyHNTWE"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}


def col_to_sql(col):
    s = col.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")


def clean_value(v):
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    return str(v) if not isinstance(v, str) else v


def upload(batch_size=50):
    df = pd.read_csv("data/combined_raw.csv")
    print(f"Loaded {len(df)} rows, {len(df.columns)} columns")

    # Rename columns to SQL names
    df.columns = [col_to_sql(c) for c in df.columns]

    total = len(df)
    uploaded = 0

    for start in range(0, total, batch_size):
        batch = df.iloc[start : start + batch_size]
        records = []
        for _, row in batch.iterrows():
            records.append({k: clean_value(v) for k, v in row.items()})

        resp = requests.post(
            f"{SUPABASE_URL}/rest/v1/products",
            headers=HEADERS,
            data=json.dumps(records),
        )

        if resp.status_code in (200, 201):
            uploaded += len(batch)
            print(f"  Uploaded {uploaded}/{total} rows")
        else:
            print(f"  ERROR at batch {start}: {resp.status_code} {resp.text[:200]}")
            return False

    print(f"\nDone. {uploaded} rows uploaded.")
    return True


if __name__ == "__main__":
    upload()
