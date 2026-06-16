"""
Supplier Risk Score Module
============================
Multi-factor risk scoring for each supplier in the dataset.

Risk Score Factors:
  - Verification Status (40%): Verified suppliers = lower risk
  - Rating Consistency (30%): Higher ratings = lower risk
  - Price Stability (20%): Lower price variance = lower risk
  - Data Freshness (10%): Recently scraped = lower risk

Output: supplier_risk_scores.json
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import datetime
from typing import Dict, List

def calculate_verification_score(verified: bool) -> float:
    """Verification status score (0-100)."""
    return 100.0 if verified else 50.0


def calculate_rating_score(rating: float, category_ratings: pd.Series) -> float:
    """
    Rating consistency score (0-100).
    Normalized against category median rating.
    """
    if pd.isna(rating):
        return 30.0  # Low score for missing rating

    category_median = category_ratings.median()
    if pd.isna(category_median) or category_median == 0:
        return float(min(rating / 5.0 * 100, 100))

    # Score based on how close to category median
    diff = abs(rating - category_median)
    score = max(0, 100 - (diff * 10))
    return float(min(score, 100))


def calculate_price_stability_score(supplier_prices: pd.Series) -> float:
    """
    Price stability score (0-100).
    Lower variance = higher score (more stable = lower risk).
    """
    if len(supplier_prices) < 2 or supplier_prices.isna().all():
        return 50.0  # Neutral score for single/missing price

    prices = supplier_prices.dropna()
    if len(prices) == 0:
        return 30.0

    # Calculate coefficient of variation (CV)
    mean_price = prices.mean()
    if mean_price == 0:
        return 50.0

    cv = (prices.std() / mean_price) * 100

    # Normalize CV to 0-100 score (lower CV = higher score)
    # CV > 50% = very unstable (score = 20)
    # CV < 10% = very stable (score = 100)
    score = max(0, 100 - (cv * 1.5))
    return float(min(score, 100))


def calculate_freshness_score(scraped_at: str) -> float:
    """
    Data freshness score (0-100).
    Recently scraped data = higher score (lower risk).
    """
    try:
        scraped_date = pd.to_datetime(scraped_at)
        now = pd.to_datetime(datetime.utcnow())
        days_old = (now - scraped_date).days

        # Score: 100 if today, decreases over time
        # 0 if > 30 days old
        score = max(0, 100 - (days_old * 3.33))
        return float(min(score, 100))
    except:
        return 50.0


def calculate_supplier_risk_scores(df: pd.DataFrame) -> Dict:
    """
    Calculate risk scores for all suppliers.

    Args:
        df: Clean DataFrame with supplier data

    Returns:
        Dict with supplier risk scores and risk levels
    """
    if df.empty:
        return {"suppliers": {}, "summary": {}}

    supplier_scores = {}

    # Group by supplier
    for supplier_name, supplier_group in df.groupby("supplier_name"):
        if supplier_name == "Unknown" or pd.isna(supplier_name):
            continue

        # Get supplier data
        category = supplier_group["category"].mode()[0] if len(supplier_group) > 0 else "Unknown"
        verified = supplier_group["verified"].any()

        # Rating score (normalized against category)
        category_ratings = df[df["category"] == category]["rating"]
        avg_rating = supplier_group["rating"].mean()
        rating_score = calculate_rating_score(avg_rating, category_ratings)

        # Price stability (across all products from this supplier)
        prices = supplier_group["price_min"].dropna()
        price_stability = calculate_price_stability_score(prices)

        # Verification score
        verification_score = calculate_verification_score(verified)

        # Freshness score (most recent scrape)
        latest_scrape = supplier_group["scraped_at"].max()
        freshness_score = calculate_freshness_score(latest_scrape)

        # Weighted composite score
        risk_score = (
            verification_score * 0.40 +
            rating_score * 0.30 +
            price_stability * 0.20 +
            freshness_score * 0.10
        )

        # Determine risk level
        if risk_score >= 80:
            risk_level = "LOW"
        elif risk_score >= 60:
            risk_level = "MEDIUM"
        elif risk_score >= 40:
            risk_level = "HIGH"
        else:
            risk_level = "CRITICAL"

        supplier_scores[supplier_name] = {
            "risk_score": round(float(risk_score), 2),
            "risk_level": risk_level,
            "factors": {
                "verification_score": round(float(verification_score), 2),
                "rating_score": round(float(rating_score), 2),
                "price_stability_score": round(float(price_stability), 2),
                "freshness_score": round(float(freshness_score), 2),
            },
            "metadata": {
                "product_count": len(supplier_group),
                "avg_rating": round(float(avg_rating), 2) if not pd.isna(avg_rating) else None,
                "verified": bool(verified),
                "primary_category": category,
                "price_range": {
                    "min": round(float(supplier_group["price_min"].min()), 2) if not supplier_group["price_min"].isna().all() else None,
                    "max": round(float(supplier_group["price_max"].max()), 2) if not supplier_group["price_max"].isna().all() else None,
                }
            }
        }

    # Calculate summary statistics
    scores = [s["risk_score"] for s in supplier_scores.values()]
    risk_levels = [s["risk_level"] for s in supplier_scores.values()]

    summary = {
        "total_suppliers": len(supplier_scores),
        "average_risk_score": round(float(np.mean(scores)), 2) if scores else 0,
        "risk_distribution": {
            "LOW": risk_levels.count("LOW"),
            "MEDIUM": risk_levels.count("MEDIUM"),
            "HIGH": risk_levels.count("HIGH"),
            "CRITICAL": risk_levels.count("CRITICAL"),
        },
        "generated_at": datetime.utcnow().isoformat(),
    }

    return {
        "suppliers": supplier_scores,
        "summary": summary,
    }


def save_risk_scores(scores: Dict, output_dir: str = "../data"):
    """Save risk scores to JSON file."""
    output_path = os.path.join(output_dir, "supplier_risk_scores.json")
    os.makedirs(output_dir, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(scores, f, indent=2)

    print(f"✅ Risk scores saved to {output_path}")
    return output_path


if __name__ == "__main__":
    # Example usage
    from etl import load_clean_data

    df = load_clean_data()
    if not df.empty:
        scores = calculate_supplier_risk_scores(df)
        save_risk_scores(scores)

        print("\n📊 Supplier Risk Score Summary:")
        print(f"Total suppliers: {scores['summary']['total_suppliers']}")
        print(f"Average risk score: {scores['summary']['average_risk_score']}")
        print(f"Risk distribution: {scores['summary']['risk_distribution']}")
