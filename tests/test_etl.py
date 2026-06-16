"""
Unit tests for ETL pipeline — validation and transformation layer
Run: pytest tests/test_etl.py -v
"""

import pytest
import pandas as pd
import numpy as np
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from etl import validate, transform, clean_location, normalize_price  # noqa


# ── Fixtures ──────────────────────────────────────────────────────────────────
@pytest.fixture
def sample_df():
    return pd.DataFrame([
        {"product_name": "CNC Machine",    "supplier_name": "ABC Ltd",  "location": "Mumbai, Maharashtra",  "category": "industrial_machinery", "price_min": 50000, "price_max": 75000, "rating": 4.2, "verified": True,  "scraped_at": "2025-01-01"},
        {"product_name": "LED Strip",      "supplier_name": "XYZ Co",   "location": "Delhi, Delhi",         "category": "electronics",           "price_min": 200,   "price_max": 500,   "rating": 3.8, "verified": False, "scraped_at": "2025-01-02"},
        {"product_name": "Cotton Fabric",  "supplier_name": "Fab Works", "location": "Surat, Gujarat",      "category": "textiles",              "price_min": 50,    "price_max": 150,   "rating": 4.5, "verified": True,  "scraped_at": "2025-01-03"},
        {"product_name": "Sulphuric Acid", "supplier_name": "Chem Co",  "location": "Ahmedabad, Gujarat",   "category": "chemicals",             "price_min": None,  "price_max": None,  "rating": None,"verified": False, "scraped_at": "2025-01-04"},
        {"product_name": None,             "supplier_name": "Ghost Co",  "location": "Unknown",             "category": "agriculture",           "price_min": 1000,  "price_max": 2000,  "rating": 4.0, "verified": True,  "scraped_at": "2025-01-05"},
    ])


@pytest.fixture
def duplicate_df():
    row = {"product_name": "CNC Machine", "supplier_name": "ABC Ltd", "location": "Mumbai, Maharashtra",
           "category": "industrial_machinery", "price_min": 50000, "price_max": 75000, "rating": 4.2,
           "verified": True, "scraped_at": "2025-01-01"}
    return pd.DataFrame([row, row, row])  # 3 identical rows


# ── Validation tests ──────────────────────────────────────────────────────────
class TestValidation:
    def test_drops_null_product_name(self, sample_df):
        df_valid, dq = validate(sample_df)
        assert df_valid["product_name"].notna().all(), "Rows with null product_name should be dropped"

    def test_dq_report_structure(self, sample_df):
        _, dq = validate(sample_df)
        assert "total_records"     in dq
        assert "overall_completeness" in dq
        assert "duplicate_count"   in dq
        assert "field_completeness" in dq

    def test_duplicate_count_detected(self, duplicate_df):
        _, dq = validate(duplicate_df)
        assert dq["duplicate_count"] >= 2, "Should detect duplicates"

    def test_returns_dataframe(self, sample_df):
        df_valid, _ = validate(sample_df)
        assert isinstance(df_valid, pd.DataFrame)

    def test_completeness_between_0_and_100(self, sample_df):
        _, dq = validate(sample_df)
        assert 0 <= dq["overall_completeness"] <= 100


# ── Transformation tests ──────────────────────────────────────────────────────
class TestTransform:
    def test_deduplication(self, duplicate_df):
        """Duplicate rows should be removed."""
        df_valid, _ = validate(duplicate_df)
        df_clean = transform(df_valid)
        assert len(df_clean) == 1, "Should deduplicate to 1 row"

    def test_city_state_parsing(self, sample_df):
        """Location should be split into city + state."""
        df_valid, _ = validate(sample_df)
        df_clean = transform(df_valid)
        assert "city"  in df_clean.columns
        assert "state" in df_clean.columns
        assert (df_clean["city"] != "").all()

    def test_price_mid_calculated(self, sample_df):
        """price_mid should be average of price_min and price_max."""
        df_valid, _ = validate(sample_df)
        df_clean = transform(df_valid)
        if "price_mid" in df_clean.columns:
            has_both = df_clean["price_min"].notna() & df_clean["price_max"].notna()
            sub = df_clean[has_both]
            expected = (sub["price_min"] + sub["price_max"]) / 2
            pd.testing.assert_series_equal(
                sub["price_mid"].reset_index(drop=True),
                expected.reset_index(drop=True),
                check_names=False, rtol=0.01
            )

    def test_keywords_generated(self, sample_df):
        """Keywords column should be created from product names."""
        df_valid, _ = validate(sample_df)
        df_clean = transform(df_valid)
        assert "keywords" in df_clean.columns
        assert df_clean["keywords"].notna().any()

    def test_price_bucket_categories(self, sample_df):
        """price_bucket should only contain valid categories."""
        df_valid, _ = validate(sample_df)
        df_clean = transform(df_valid)
        if "price_bucket" in df_clean.columns:
            valid = {"<₹100", "₹100-500", "₹500-1K", "₹1K-5K", "₹5K-10K", ">₹10K"}
            actual = set(df_clean["price_bucket"].dropna().astype(str).unique())
            assert actual.issubset(valid), f"Unexpected buckets: {actual - valid}"

    def test_verified_is_boolean(self, sample_df):
        """verified column should be boolean type."""
        df_valid, _ = validate(sample_df)
        df_clean = transform(df_valid)
        if "verified" in df_clean.columns:
            assert df_clean["verified"].dtype == bool


# ── Location parsing tests ────────────────────────────────────────────────────
class TestCleanLocation:
    def test_city_state_split(self):
        city, state = clean_location("Mumbai, Maharashtra")
        assert city  == "Mumbai"
        assert state == "Maharashtra"

    def test_city_only_lookup(self):
        city, state = clean_location("Mumbai")
        assert city  == "Mumbai"
        assert state == "Maharashtra"  # from STATE_MAP

    def test_unknown_location(self):
        city, state = clean_location("Unknown")
        assert city  == "Unknown"
        assert state == "Unknown"

    def test_empty_location(self):
        city, state = clean_location("")
        assert city  == "Unknown"

    def test_bangalore_alias(self):
        city, state = clean_location("Bangalore")
        assert state == "Karnataka"


# ── Price normalisation tests ─────────────────────────────────────────────────
class TestNormalizePrice:
    def test_fills_max_from_min(self):
        row = pd.Series({"price_min": 500.0, "price_max": None})
        result = normalize_price(row)
        assert result["price_max"] == 500.0

    def test_calculates_mid(self):
        row = pd.Series({"price_min": 100.0, "price_max": 200.0})
        result = normalize_price(row)
        assert result["price_mid"] == 150.0

    def test_range_flag_range(self):
        row = pd.Series({"price_min": 100.0, "price_max": 200.0})
        result = normalize_price(row)
        assert result["price_range_flag"] == "range"

    def test_range_flag_fixed(self):
        row = pd.Series({"price_min": 500.0, "price_max": 500.0})
        result = normalize_price(row)
        assert result["price_range_flag"] == "fixed"

    def test_both_null(self):
        row = pd.Series({"price_min": None, "price_max": None})
        result = normalize_price(row)
        assert result["price_range_flag"] == "unknown"
        assert pd.isna(result["price_mid"])


# ── Integration test ──────────────────────────────────────────────────────────
class TestIntegration:
    def test_full_pipeline(self, sample_df):
        """Full validate → transform should produce a clean, non-empty DataFrame."""
        df_valid, dq = validate(sample_df)
        df_clean = transform(df_valid)
        assert len(df_clean) > 0, "Pipeline should produce records"
        assert "city"  in df_clean.columns
        assert "state" in df_clean.columns
        assert df_clean["product_name_clean"].notna().all()

    def test_no_duplicate_products(self, duplicate_df):
        """Pipeline should eliminate exact duplicates."""
        df_valid, _ = validate(duplicate_df)
        df_clean = transform(df_valid)
        assert df_clean.duplicated(subset=["product_name_clean", "supplier_name", "city"]).sum() == 0
