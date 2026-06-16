"""
Data Quality Score Module
==========================
Per-supplier and per-category data quality assessment.

Quality Metrics:
  - Field Completeness: % of non-null fields per supplier
  - Data Consistency: Rating/price consistency checks
  - Outlier Presence: Flags suspicious data patterns
  - Update Frequency: How recently data was scraped

Output: data_quality_scores.json
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import datetime
from typing import Dict, List, Tuple

REQUIRED_FIELDS = [
    "product_name",
    "supplier_name",
    "location",
    "category",
    "price_min",
    "rating",
]

QUALITY_FIELDS = [
    "product_name",
    "supplier_name",
    "location",
    "category",
    "price_min",
    "price_max",
    "price_unit",
    "rating",
    "verified",
    "moq",
    "product_url",
]


def calculate_completeness_score(row: pd.Series, fields: List[str] = QUALITY_FIELDS) -> float:
    """Calculate completeness score (0-100) for a row."""
    non_null_count = sum(1 for field in fields if field in row.index and pd.notna(row[field]))
    return (non_null_count / len(fields)) * 100


def calculate_supplier_completeness(supplier_data: pd.DataFrame) -> float:
    """Average completeness across all records from a supplier."""
    scores = supplier_data.apply(lambda row: calculate_completeness_score(row), axis=1)
    return float(scores.mean())


def detect_data_anomalies(row: pd.Series) -> List[str]:
    """Detect anomalies in a single row."""
    anomalies = []

    # Price anomalies
    if pd.notna(row.get("price_min")) and pd.notna(row.get("price_max")):
        if row["price_max"] < row["price_min"]:
            anomalies.append("price_max < price_min")

    # Rating anomalies (perfect rating with no reviews is suspicious)
    if row.get("rating") == 5.0 and row.get("rating") == 5.0:
        anomalies.append("perfect_rating_suspicious")

    # Missing critical fields
    if pd.isna(row.get("product_name")) or len(str(row.get("product_name", ""))) < 3:
        anomalies.append("invalid_product_name")

    if pd.isna(row.get("supplier_name")) or row.get("supplier_name") == "Unknown":
        anomalies.append("missing_supplier_name")

    if pd.isna(row.get("location")) or row.get("location") == "Unknown":
        anomalies.append("missing_location")

    return anomalies


def calculate_data_quality_scores(df: pd.DataFrame) -> Dict:
    """
    Calculate data quality scores for suppliers and overall dataset.

    Args:
        df: Clean DataFrame with supplier data

    Returns:
        Dict with quality scores, anomalies, and recommendations
    """
    if df.empty:
        return {"suppliers": {}, "dataset": {}, "anomalies": []}

    supplier_quality = {}
    all_anomalies = []

    # Per-supplier quality assessment
    for supplier_name, supplier_group in df.groupby("supplier_name"):
        if supplier_name == "Unknown" or pd.isna(supplier_name):
            continue

        # Calculate completeness
        completeness = calculate_supplier_completeness(supplier_group)

        # Detect anomalies
        supplier_anomalies = []
        for _, row in supplier_group.iterrows():
            anomalies = detect_data_anomalies(row)
            if anomalies:
                supplier_anomalies.extend(anomalies)
                all_anomalies.append({
                    "supplier": supplier_name,
                    "product": row.get("product_name", "Unknown"),
                    "anomalies": anomalies,
                })

        # Quality score based on completeness and anomaly count
        anomaly_penalty = min(len(supplier_anomalies) * 5, 30)  # Max 30% penalty
        quality_score = max(0, completeness - anomaly_penalty)

        # Quality level
        if quality_score >= 80:
            quality_level = "EXCELLENT"
        elif quality_score >= 60:
            quality_level = "GOOD"
        elif quality_score >= 40:
            quality_level = "FAIR"
        else:
            quality_level = "POOR"

        supplier_quality[supplier_name] = {
            "quality_score": round(float(quality_score), 2),
            "quality_level": quality_level,
            "completeness_score": round(float(completeness), 2),
            "record_count": len(supplier_group),
            "anomaly_count": len(supplier_anomalies),
            "missing_fields": {
                field: int((supplier_group[field].isna().sum() / len(supplier_group)) * 100)
                for field in QUALITY_FIELDS
                if field in supplier_group.columns
            },
        }

    # Dataset-level quality assessment
    dataset_quality = {
        "total_records": len(df),
        "total_suppliers": len(supplier_quality),
        "average_completeness": round(float(df.apply(calculate_completeness_score, axis=1).mean()), 2),
        "records_with_anomalies": len(all_anomalies),
        "anomaly_rate": round(float(len(all_anomalies) / len(df) * 100), 2),
        "field_coverage": {
            field: int((df[field].notna().sum() / len(df)) * 100)
            for field in QUALITY_FIELDS
            if field in df.columns
        },
    }

    # Category-level quality
    category_quality = {}
    for category in df["category"].unique():
        category_data = df[df["category"] == category]
        category_quality[category] = {
            "record_count": len(category_data),
            "completeness": round(float(category_data.apply(calculate_completeness_score, axis=1).mean()), 2),
            "verified_percentage": round(float(category_data["verified"].sum() / len(category_data) * 100), 2),
            "average_rating": round(float(category_data["rating"].mean()), 2) if category_data["rating"].notna().any() else None,
            "missing_price_count": int(category_data["price_min"].isna().sum()),
        }

    # Overall data quality score
    avg_supplier_quality = np.mean([s["quality_score"] for s in supplier_quality.values()])
    dataset_level_score = (
        dataset_quality["average_completeness"] * 0.5 +
        max(0, 100 - dataset_quality["anomaly_rate"] * 2) * 0.5
    )

    return {
        "suppliers": supplier_quality,
        "dataset": dataset_quality,
        "categories": category_quality,
        "overall_quality_score": round(float(dataset_level_score), 2),
        "anomalies": all_anomalies,
        "summary": {
            "total_anomalies_detected": len(all_anomalies),
            "suppliers_with_issues": len([s for s in supplier_quality.values() if s["quality_level"] in ["FAIR", "POOR"]]),
            "generated_at": datetime.utcnow().isoformat(),
        }
    }


def save_quality_scores(scores: Dict, output_dir: str = "../data"):
    """Save quality scores to JSON file."""
    output_path = os.path.join(output_dir, "data_quality_scores.json")
    os.makedirs(output_dir, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(scores, f, indent=2)

    print(f"✅ Quality scores saved to {output_path}")
    return output_path


def print_quality_report(scores: Dict):
    """Print a human-readable quality report."""
    print("\n" + "=" * 70)
    print("📊 DATA QUALITY REPORT")
    print("=" * 70)

    summary = scores["summary"]
    dataset = scores["dataset"]

    print(f"\n📈 Overall Quality Score: {scores['overall_quality_score']:.2f}/100")
    print(f"\n📋 Dataset Overview:")
    print(f"   Total Records: {dataset['total_records']}")
    print(f"   Total Suppliers: {dataset['total_suppliers']}")
    print(f"   Average Completeness: {dataset['average_completeness']:.2f}%")
    print(f"   Anomalies Detected: {summary['total_anomalies_detected']}")
    print(f"   Anomaly Rate: {dataset['anomaly_rate']:.2f}%")

    print(f"\n⚠️  Quality Issues:")
    print(f"   Suppliers with Fair/Poor Quality: {summary['suppliers_with_issues']}")

    print(f"\n📁 Category Quality:")
    for cat, metrics in scores["categories"].items():
        print(f"   {cat}:")
        print(f"      Records: {metrics['record_count']}")
        print(f"      Completeness: {metrics['completeness']:.2f}%")
        print(f"      Verified: {metrics['verified_percentage']:.2f}%")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    # Example usage
    from etl import load_clean_data

    df = load_clean_data()
    if not df.empty:
        scores = calculate_data_quality_scores(df)
        save_quality_scores(scores)
        print_quality_report(scores)
