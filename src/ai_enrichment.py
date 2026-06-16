"""
AI Product Enrichment using Qwen 2.5 7B (local via LM Studio)
==============================================================
Enriches TradeIndia rows with AI-extracted structured fields:
  - ai_product_type  : e.g. "Industrial Textiles", "Test Equipment"
  - ai_material      : e.g. "Fiberglass", "Jute", "Copper"
  - ai_use_case      : e.g. "Textile Manufacturing", "Quality Testing"
  - ai_business_role : e.g. "Manufacturer", "Exporter", "Trader"

Requirements:
  - LM Studio running at http://localhost:1234
  - Qwen 2.5 7B model loaded in LM Studio

Run:
  python src/ai_enrichment.py
"""

import requests
import pandas as pd
import json
import time
import re
import os

LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"
SUPABASE_URL  = "https://ayioshdnrdbevujphscb.supabase.co"
SUPABASE_KEY  = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImF5aW9zaGRucmRiZXZ1anBoc2NiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODE2MDM2MzMsImV4cCI6MjA5NzE3OTYzM30.EULHrH2MYDuNh3U59LIdoWlspl0soUsJHeq0eyHNTWE"
PROGRESS_FILE = "data/ai_enrichment_progress.json"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

PROMPT_TEMPLATE = """You are a B2B supply chain data analyst. Extract structured information from this product name.

Product: "{product_name}"

Return ONLY a JSON object with these exact keys (no explanation, no markdown):
{{
  "ai_product_type": "<broad product category, e.g. Industrial Textiles, Test Equipment, Textile Machinery, Cables & Wires, Dyes & Chemicals, Raw Materials>",
  "ai_material": "<primary material if identifiable, else null>",
  "ai_use_case": "<primary application or industry, e.g. Textile Manufacturing, Quality Testing, Electrical Wiring>",
  "ai_business_role": "<Manufacturer, Exporter, Trader, Supplier, or Service Provider — infer from product name>"
}}"""


def check_lm_studio():
    try:
        r = requests.get("http://localhost:1234/v1/models", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def extract_with_qwen(product_name: str) -> dict:
    payload = {
        "model": "local-model",
        "messages": [{"role": "user", "content": PROMPT_TEMPLATE.format(product_name=product_name)}],
        "temperature": 0.1,
        "max_tokens": 150,
    }
    try:
        r = requests.post(LM_STUDIO_URL, json=payload, timeout=30)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"].strip()
        match = re.search(r'\{.*?\}', content, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception as e:
        print(f"    [warn] {e}")
    return {"ai_product_type": None, "ai_material": None, "ai_use_case": None, "ai_business_role": None}


def load_progress() -> dict:
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {}


def save_progress(progress: dict):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)


def update_supabase_by_name(product_name: str, enrichment: dict):
    encoded = requests.utils.quote(product_name)
    r = requests.patch(
        f"{SUPABASE_URL}/rest/v1/products?productname=eq.{encoded}&source=eq.TradeIndia",
        headers={**HEADERS, "Prefer": "return=minimal"},
        json=enrichment,
    )
    return r.status_code in (200, 204)


def run():
    if not check_lm_studio():
        print("LM Studio is not running at http://localhost:1234")
        print("Please open LM Studio, load Qwen 2.5 7B, and start the server.")
        return

    print("LM Studio connected.")

    df = pd.read_csv("data/combined_raw.csv")
    tradeindia = df[df["source"] == "TradeIndia"].copy()
    unique_names = tradeindia["productName"].dropna().unique()
    print(f"Processing {len(unique_names)} unique TradeIndia products ({len(tradeindia)} total rows)...")

    progress = load_progress()
    already_done = sum(1 for v in progress.values() if v.get("ai_product_type"))
    if already_done:
        print(f"Resuming — {already_done} products already done.")

    done = 0
    for name in unique_names:
        if name in progress and progress[name].get("ai_product_type"):
            continue

        print(f"  [{done+1}/{len(unique_names)}] {name[:70]}")
        enrichment = extract_with_qwen(name)
        progress[name] = enrichment

        update_supabase_by_name(name, enrichment)
        save_progress(progress)
        done += 1
        time.sleep(0.3)

    print(f"\nDone. {done} unique products enriched ({len(tradeindia)} rows updated in Supabase).")
    print(f"Progress saved to {PROGRESS_FILE}")

    results = pd.DataFrame(progress).T
    print("\nSample results:")
    print(results.head(10).to_string())


if __name__ == "__main__":
    run()
