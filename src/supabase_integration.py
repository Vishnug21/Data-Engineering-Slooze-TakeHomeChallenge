"""
Supabase Integration Module
============================
Upload combined data and analysis results to Supabase PostgreSQL.

Usage:
    python src/supabase_integration.py
"""

import pandas as pd
import os
import json
from sqlalchemy import create_engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Supabase connection details
SUPABASE_URL = "postgresql://postgres"
SUPABASE_HOST = "db.ayioshdnrdbevujphscb.supabase.co"
SUPABASE_PORT = 5432
SUPABASE_DB = "postgres"
SUPABASE_USER = "postgres"

def get_connection_string(password: str) -> str:
    """Build PostgreSQL connection string."""
    return f"postgresql://{SUPABASE_USER}:{password}@{SUPABASE_HOST}:{SUPABASE_PORT}/{SUPABASE_DB}"

def upload_to_supabase(password: str) -> bool:
    """Upload combined data to Supabase."""
    try:
        connection_string = get_connection_string(password)
        engine = create_engine(connection_string)

        # Load combined data
        df = pd.read_csv("data/combined_raw.csv")

        logger.info(f"Uploading {len(df)} rows to Supabase...")

        # Upload main table
        df.to_sql("products", engine, if_exists="replace", index=False)
        logger.info("✓ Uploaded products table")

        # Create metadata table
        metadata = {
            "total_records": len(df),
            "sources": df['source'].value_counts().to_dict(),
            "categories": df['category'].value_counts().to_dict() if 'category' in df.columns else {},
            "timestamp": str(pd.Timestamp.now()),
        }

        metadata_df = pd.DataFrame([metadata])
        metadata_df.to_sql("metadata", engine, if_exists="replace", index=False)
        logger.info("✓ Uploaded metadata table")

        return True

    except Exception as e:
        logger.error(f"Error uploading to Supabase: {e}")
        return False

def query_products(password: str, limit: int = 100) -> pd.DataFrame:
    """Query products from Supabase."""
    try:
        connection_string = get_connection_string(password)
        engine = create_engine(connection_string)

        query = f"SELECT * FROM products LIMIT {limit}"
        df = pd.read_sql(query, engine)

        logger.info(f"Retrieved {len(df)} rows from Supabase")
        return df

    except Exception as e:
        logger.error(f"Error querying Supabase: {e}")
        return None

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python src/supabase_integration.py <password>")
        print("\nExample:")
        print("  python src/supabase_integration.py your_supabase_password")
        sys.exit(1)

    password = sys.argv[1]

    print("Uploading data to Supabase...")
    if upload_to_supabase(password):
        print("[OK] Upload successful!")

        print("\nVerifying upload...")
        df = query_products(password, limit=5)
        if df is not None:
            print(f"Sample data:\n{df.head()}")
    else:
        print("[ERROR] Upload failed. Check your password and connection.")
