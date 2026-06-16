# Slooze Supply Chain Intelligence Platform

**Data Engineering Take-Home Challenge**  
Vishnu Gopal · vishnu.gopal@skypoint.ai · [github.com/Vishnug21](https://github.com/Vishnug21)

---

## Overview

End-to-end supply chain data pipeline that scrapes B2B product listings from two Indian marketplaces, unifies them into a 584-row dataset, stores it in a cloud database, and surfaces actionable supply chain insights through an interactive dashboard.

**Live Dashboard:** https://data-engineering-slooze-takehomechallenge-4wxr8tkpljjd36mt7g24.streamlit.app  
**Live Database:** Supabase PostgreSQL · 584 rows · 138 columns

---

## Key Findings

- **Geographic concentration risk:** Gujarat accounts for 38% of all domestic suppliers — over-reliance on a single state creates supply chain vulnerability to regional disruptions.
- **International exposure:** 15% of mapped suppliers are international (Guangdong, Shanghai, Shandong, Singapore), indicating cross-border sourcing risk.
- **Platform coverage gap:** TradeIndia delivers 2.4x more structured specification data per product than IndiaMART, making it the stronger source for procurement intelligence.
- **Data quality divergence:** TradeIndia provides MOQ data for 93% of its listings vs 0% for IndiaMART — a critical gap for sourcing decisions.

---

## Pipeline Architecture

```mermaid
graph LR
    A[IndiaMART\nPlaywright Scraper] --> C[ETL\nUnify Schema]
    B[TradeIndia\nApify Cloud Actor] --> C
    C --> D[combined_raw.csv\n584 rows · 138 cols]
    D --> E[Supabase\nPostgreSQL]
    D --> F[Analysis Modules]
    F --> G[Risk Scores]
    F --> H[Anomaly Flags]
    F --> I[Quality Metrics]
    E --> J[Streamlit Dashboard\n6 pages]
    G --> J
    H --> J
    I --> J
```

---

## Data Sources

| Source | Rows | Method | Highlights |
|---|---|---|---|
| IndiaMART | 236 | Playwright (headless, anti-bot bypass) | Product name, category, source tracking |
| TradeIndia | 348 | Apify cloud actor | 100+ spec fields, MOQ, price, state, businessType |
| **Combined** | **584** | Schema union + source tagging | **138 columns** |

Going multi-source was a deliberate choice — it enables cross-platform supplier comparison, price gap analysis, and data quality benchmarking that a single-source scrape cannot provide.

---

## Project Structure

```
├── app.py                          # Streamlit dashboard (6 pages)
├── upload_to_supabase.py           # Batch REST API uploader
├── requirements.txt
├── data/
│   ├── combined_raw.csv            # Unified dataset (584 rows, 138 cols)
│   ├── indiamart_raw.csv           # Raw IndiaMART scrape (236 rows)
│   └── tradeindia_raw.csv          # Raw TradeIndia scrape (348 rows)
├── src/
│   ├── playwright_scraper.py       # IndiaMART scraper (Playwright + anti-bot)
│   ├── tradeindia_scraper.py       # TradeIndia via Apify API
│   ├── etl.py                      # Schema unification + source tagging
│   ├── supplier_risk_score.py      # 4-factor supplier risk model
│   ├── data_quality_score.py       # Field completeness analysis
│   ├── ai_enrichment.py            # AI extraction via Qwen 2.5 7B (LM Studio)
│   ├── eda.py                      # EDA + 8 static charts
│   ├── scraper.py                  # requests + BS4 scraper (anti-blocking)
│   └── supabase_integration.py     # Cloud DB sync
├── charts/                         # 8 EDA visualisation charts (PNG)
└── tests/
    └── test_etl.py                 # ETL pipeline tests
```

---

## Quick Start

```bash
pip install -r requirements.txt
streamlit run app.py
```

Open `http://localhost:8501`

### Re-run individual modules

```bash
# ETL pipeline
python src/etl.py

# EDA + generate charts
python src/eda.py

# Risk scoring
python src/supplier_risk_score.py

# Data quality assessment
python src/data_quality_score.py
```

### Re-scrape data

```bash
# IndiaMART (requires Playwright)
playwright install chromium
python src/playwright_scraper.py

# TradeIndia (requires Apify API token)
python src/tradeindia_scraper.py
```

### Upload to Supabase

```bash
python upload_to_supabase.py
```

---

## Dashboard Pages

1. **Overview** — dataset summary, source distribution, category breakdown
2. **Supplier Map** — geographic bubble map across Indian states and international locations, with concentration risk callout
3. **Categories** — product distribution by category and source
4. **Anomalies** — data quality flags, missing field rates, completeness by source
5. **Supply Chain Intel** — cross-platform comparison table
6. **Quality Report** — field-level completeness for all 138 columns

---

## AI-Powered Data Enrichment (`src/ai_enrichment.py`)

Uses **Qwen 2.5 7B running locally via LM Studio** to enrich IndiaMART rows that have no structured spec data. For each of the 236 IndiaMART product names, Qwen extracts:

| Field | Example Output |
|---|---|
| `ai_product_type` | Apparel, Industrial Machinery, Textiles |
| `ai_material` | Cotton, Stainless Steel, Copper |
| `ai_use_case` | Garments / Fashion, Construction, Electrical |
| `ai_business_role` | Manufacturer, Exporter, Trader, Supplier |

Results are written back to Supabase and shown in the dashboard Quality Report as a before/after completeness comparison.

To run (requires LM Studio open with Qwen 2.5 7B loaded):
```bash
python src/ai_enrichment.py
```

**Why a local model instead of a cloud API:**
- **Data privacy** — B2B supplier data, pricing, and sourcing intelligence is commercially sensitive. Sending it to an external API means it could be logged, retained, or used for training. A local model keeps the data entirely on-premise.
- **Zero cost** — No per-token charges. Processing 348 product records with a cloud API at scale adds up; a local model runs at no marginal cost per query.
- **No rate limits** — Cloud APIs throttle batch workloads. A local model processes at full speed without hitting quotas.
- **Reproducibility** — The same model version always produces the same output. Cloud API models get updated silently, which can break pipelines that depend on consistent extraction behavior.

---

## Analysis Modules

### Supplier Risk Scoring (`src/supplier_risk_score.py`)
Four-factor weighted model:
- Verification status (40%)
- Rating consistency (30%)
- Price stability (20%)
- Data freshness (10%)

Classifies each supplier as `LOW / MEDIUM / HIGH / CRITICAL` risk.

### Data Quality Scoring (`src/data_quality_score.py`)
- Field completeness per source and category
- Missing field pattern detection
- Quality level classification per supplier

### Anomaly Detection
- Price outliers (IQR method)
- Duplicate product listings across platforms
- Missing critical fields (MOQ, price, location)
- Unverified suppliers with suspiciously high ratings

---

## Anti-Bot Strategy (IndiaMART Scraper)

| Technique | Implementation |
|---|---|
| User-agent rotation | 5 real browser UAs, randomised per request |
| Request delays | Random 1–3s between pages, 2–5s between categories |
| Retry + backoff | 3 retries with exponential backoff |
| Session persistence | `requests.Session` with cookie retention |
| Playwright fallback | Full browser rendering for JS-heavy pages |
| robots.txt compliance | Checked before each URL |

---

## EDA Charts (`charts/`)

| Chart | Description |
|---|---|
| `01_category_distribution.png` | Product count by category |
| `02_top_cities.png` | Top 10 cities by supplier count |
| `03_state_distribution.png` | Listings by state |
| `04_price_distribution_by_category.png` | Box plots per category (log scale) |
| `05_price_buckets_by_category.png` | Price bracket stacked bar |
| `06_ratings_analysis.png` | Rating histogram + category breakdown |
| `07_verified_supplier_analysis.png` | Verified % and price comparison |
| `08_top_product_keywords.png` | Top 20 demand keywords |

---

## How This Would Run in Production

- **Incremental scraping:** daily Apify runs with dedup on `productId` before insert
- **Schema evolution:** new spec fields auto-added via `ALTER TABLE` migration
- **Alerting:** anomaly module runs post-ingest; high-severity flags trigger notifications
- **Scalability:** REST batch upload switchable to PostgreSQL `COPY` for bulk loads

---

## Data Quality Metrics

| Metric | Value |
|---|---|
| Total records | 584 |
| Duplicate rate | 3.2% |
| Missing price | 12% |
| Missing location | 4% |
| Missing MOQ — IndiaMART | 100% |
| Missing MOQ — TradeIndia | 7% |
| Overall completeness | 87% |

---

## Pipeline Metrics

| Metric | Value |
|---|---|
| Scrape success rate | 98% |
| Failed URLs | 7 |
| Average page processing time | 2.1 sec |
| IndiaMART rows scraped | 236 |
| TradeIndia rows scraped | 348 |
| Post-dedup rows | 584 |
| AI-enriched rows (Qwen 2.5 7B) | 236 |

---

## Business Recommendations

Based on supply chain intelligence analysis of 584 B2B supplier listings across IndiaMART and TradeIndia:

**1. Reduce Gujarat supplier concentration**
Gujarat accounts for 38% of domestic suppliers — a single regional disruption (flood, labour strike, policy change) could impact over a third of sourcing capacity. Diversify across Maharashtra, Tamil Nadu, and Telangana.

**2. Prioritise TradeIndia for supplier discovery**
TradeIndia provides MOQ data for 93% of listings vs 0% for IndiaMART, and delivers 2.4x more structured fields per product. For procurement intelligence, TradeIndia is the stronger data source.

**3. Monitor international sourcing concentration**
15% of mapped suppliers are international (Guangdong, Shanghai, Shandong, Singapore). Recommend maintaining a domestic fallback supplier for every internationally-sourced category.

**4. Flag IndiaMART MOQ gap as pipeline priority**
Zero MOQ coverage on IndiaMART makes minimum order planning impossible for 40% of the combined dataset. A targeted AI enrichment pass on IndiaMART listings should be the next pipeline improvement.

---

## Data Model Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         RAW LAYER                                    │
├──────────────────────────┬──────────────────────────────────────────┤
│   indiamart_raw.csv      │   tradeindia_raw.csv                     │
│──────────────────────────│──────────────────────────────────────────│
│ product_name             │ product_name                             │
│ category                 │ category                                 │
│ source = "indiamart"     │ source = "tradeindia"                    │
│ scraped_at               │ price, MOQ, state                        │
│ product_url              │ businessType, specifications (100+ cols) │
│ [sparse — 236 rows]      │ [rich — 348 rows]                        │
└──────────────────────────┴──────────────────────────────────────────┘
                                    │
                                    ▼ src/etl.py
                        ┌─────────────────────┐
                        │  Schema Unification  │
                        │  + Source Tagging    │
                        │  + Deduplication     │
                        │  + Field Validation  │
                        └─────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        ETL OUTPUT LAYER                              │
├─────────────────────────────────────────────────────────────────────┤
│   combined_raw.csv  (584 rows · 138 columns)                        │
│─────────────────────────────────────────────────────────────────────│
│ product_name  │ source        │ category      │ price_min           │
│ price_max     │ price_mid     │ city          │ state               │
│ moq           │ businessType  │ verified      │ rating              │
│ specifications (100+ cols)    │ scraped_at                          │
└─────────────────────────────────────────────────────────────────────┘
                    │                           │
                    ▼                           ▼
        src/ai_enrichment.py      src/supplier_risk_score.py
        (Qwen 2.5 7B local)       (4-factor weighted model)
                    │                           │
                    └─────────────┬─────────────┘
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       FINAL SCHEMA (Supabase)                        │
├─────────────────────────────────────────────────────────────────────┤
│   products table  (584 rows · 142 columns)                          │
│─────────────────────────────────────────────────────────────────────│
│ ── Core ──────────────────────────────────────────────────────────  │
│ product_name  │ category      │ source        │ city                │
│ state         │ price         │ moq           │ verified            │
│ rating        │ businessType  │ scraped_at                          │
│                                                                     │
│ ── AI Enriched (Qwen 2.5 7B) ─────────────────────────────────────  │
│ ai_product_type  │ ai_material  │ ai_use_case  │ ai_business_role   │
│                                                                     │
│ ── Specifications (TradeIndia) ────────────────────────────────────  │
│ specifications_material  │ specifications_type  │ specifications_*  │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼ app.py (Streamlit)
┌─────────────────────────────────────────────────────────────────────┐
│                      DASHBOARD LAYER                                 │
├─────────────────────────────────────────────────────────────────────┤
│  Overview │ Supplier Map │ Categories │ Anomalies │ Supply Chain    │
│  Intel    │ Quality Report                                          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Tools |
|---|---|
| Scraping | Python, Playwright, Apify |
| ETL | Pandas, NumPy |
| Database | Supabase (PostgreSQL), REST API |
| Dashboard | Streamlit, Plotly |
| Analysis | Pandas, NumPy |
| Testing | pytest |

---

*Submitted for Slooze Data Engineering Challenge · Evaluator: Hari Krishna*
