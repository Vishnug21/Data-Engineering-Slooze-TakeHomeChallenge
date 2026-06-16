"""
IndiaMART B2B Marketplace Scraper
==================================
Scrapes product listings across multiple categories:
  - Industrial Machinery
  - Electronics & Electrical
  - Textiles & Apparel
  - Chemicals & Fertilizers

Anti-blocking measures:
  - Rotating User-Agent headers
  - Randomized request delays (1-3s)
  - Session-based requests with persistent cookies
  - Retry logic with exponential backoff
  - robots.txt compliance checks

Output: JSON + CSV in /data/
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
import time
import random
import logging
import os
import re
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin, urlencode
from urllib.robotparser import RobotFileParser

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
BASE_URL = "https://dir.indiamart.com/search.mp"

CATEGORIES = {
    "industrial_machinery": "industrial machinery",
    "electronics":          "electronics components",
    "textiles":             "textile fabric",
    "chemicals":            "industrial chemicals",
    "agriculture":          "agricultural equipment",
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
]

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
PAGES_PER_CATEGORY = 3
DELAY_MIN = 1.0
DELAY_MAX = 3.0
MAX_RETRIES = 3


# ── Robots.txt compliance ─────────────────────────────────────────────────────
def can_fetch(url: str) -> bool:
    """Check robots.txt before scraping."""
    try:
        rp = RobotFileParser()
        robots_url = "https://dir.indiamart.com/robots.txt"
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch("*", url)
    except Exception:
        return True  # Fail open if robots.txt unreachable


# ── HTTP helpers ──────────────────────────────────────────────────────────────
def make_session() -> requests.Session:
    """Create a requests session with rotating headers."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.9,hi;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": "https://www.google.com/",
        "DNT": "1",
    })
    return session


def fetch_page(session: requests.Session, url: str, retries: int = MAX_RETRIES) -> Optional[str]:
    """Fetch a page with retry + exponential backoff."""
    for attempt in range(retries):
        try:
            delay = random.uniform(DELAY_MIN, DELAY_MAX)
            time.sleep(delay)

            # Rotate user agent on each retry
            session.headers["User-Agent"] = random.choice(USER_AGENTS)

            response = session.get(url, timeout=20)
            response.raise_for_status()

            logger.info(f"✅ [{response.status_code}] {url}")
            return response.text

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                logger.warning(f"⚠️  403 on attempt {attempt+1} — backing off")
                time.sleep(2 ** attempt * 2)
            elif e.response.status_code == 429:
                logger.warning(f"⚠️  429 Rate limited — sleeping 30s")
                time.sleep(30)
            else:
                logger.error(f"HTTP error: {e}")
                break

        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed (attempt {attempt+1}): {e}")
            time.sleep(2 ** attempt)

    logger.error(f"❌ Failed to fetch after {retries} retries: {url}")
    return None


# ── Parsers ───────────────────────────────────────────────────────────────────
def parse_price(price_text: str) -> dict:
    """Normalize price strings like '₹500 - ₹1,000 / Piece' into structured dict."""
    if not price_text:
        return {"price_min": None, "price_max": None, "unit": None, "currency": "INR"}

    price_text = price_text.strip()
    currency = "INR" if "₹" in price_text else "USD" if "$" in price_text else "INR"

    # Extract numbers
    numbers = re.findall(r"[\d,]+(?:\.\d+)?", price_text.replace(",", ""))
    numbers = [float(n.replace(",", "")) for n in numbers if n]

    # Extract unit
    unit_match = re.search(r"/\s*([A-Za-z\s]+)$", price_text)
    unit = unit_match.group(1).strip() if unit_match else "Unit"

    return {
        "price_min": numbers[0] if numbers else None,
        "price_max": numbers[1] if len(numbers) > 1 else numbers[0] if numbers else None,
        "unit": unit,
        "currency": currency,
    }


def parse_product_card(card, category: str) -> Optional[dict]:
    """Extract structured data from a single product listing card."""
    try:
        # Product name
        name_el = (
            card.find("h2") or
            card.find(class_=re.compile(r"prd-name|product-title|name", re.I))
        )
        product_name = name_el.get_text(strip=True) if name_el else None
        if not product_name:
            return None

        # Supplier name
        supplier_el = card.find(class_=re.compile(r"company|supplier|seller", re.I))
        supplier_name = supplier_el.get_text(strip=True) if supplier_el else "Unknown"

        # Location
        loc_el = card.find(class_=re.compile(r"location|city|place", re.I))
        location = loc_el.get_text(strip=True) if loc_el else "Unknown"

        # Price
        price_el = card.find(class_=re.compile(r"price|cost|rate", re.I))
        price_raw = price_el.get_text(strip=True) if price_el else ""
        price_data = parse_price(price_raw)

        # Rating / reviews
        rating_el = card.find(class_=re.compile(r"rating|star|review", re.I))
        rating_text = rating_el.get_text(strip=True) if rating_el else ""
        rating_nums = re.findall(r"\d+\.?\d*", rating_text)
        rating = float(rating_nums[0]) if rating_nums else None

        # MOQ (Minimum Order Quantity)
        moq_el = card.find(string=re.compile(r"min.*order|moq", re.I))
        moq = moq_el.parent.get_text(strip=True) if moq_el else None

        # Product URL
        link_el = card.find("a", href=True)
        product_url = urljoin("https://www.indiamart.com", link_el["href"]) if link_el else None

        # Verified supplier badge
        verified = bool(card.find(class_=re.compile(r"verified|trust", re.I)))

        return {
            "product_name":  product_name,
            "supplier_name": supplier_name,
            "location":      location,
            "category":      category,
            "price_min":     price_data["price_min"],
            "price_max":     price_data["price_max"],
            "price_unit":    price_data["unit"],
            "currency":      price_data["currency"],
            "rating":        rating,
            "moq":           moq,
            "verified":      verified,
            "product_url":   product_url,
            "scraped_at":    datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.debug(f"Card parse error: {e}")
        return None


def scrape_category(session: requests.Session, category_key: str, search_term: str) -> list[dict]:
    """Scrape multiple pages for a single category."""
    results = []
    logger.info(f"\n📦 Scraping category: {category_key}")

    for page in range(1, PAGES_PER_CATEGORY + 1):
        params = {"ss": search_term, "page": page}
        url = f"{BASE_URL}?{urlencode(params)}"

        if not can_fetch(url):
            logger.warning(f"robots.txt disallows: {url}")
            continue

        html = fetch_page(session, url)
        if not html:
            logger.warning(f"Skipping page {page} — no content returned")
            continue

        soup = BeautifulSoup(html, "lxml")

        # Try multiple card selectors (IndiaMART structure varies)
        cards = (
            soup.find_all("div", class_=re.compile(r"product-card|lst-card|prd-card|card-body", re.I)) or
            soup.find_all("div", attrs={"data-name": True}) or
            soup.find_all("li", class_=re.compile(r"product|listing", re.I))
        )

        logger.info(f"  Page {page}: found {len(cards)} cards")

        for card in cards:
            record = parse_product_card(card, category_key)
            if record:
                results.append(record)

    return results


# ── Entry point ───────────────────────────────────────────────────────────────
def run_scraper() -> pd.DataFrame:
    """Run the full scraping pipeline across all categories."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    session = make_session()
    all_records = []

    logger.info("🚀 Starting IndiaMART scraper")
    logger.info(f"Categories: {list(CATEGORIES.keys())}")
    logger.info(f"Pages per category: {PAGES_PER_CATEGORY}")

    for cat_key, search_term in CATEGORIES.items():
        records = scrape_category(session, cat_key, search_term)
        all_records.extend(records)
        logger.info(f"✅ {cat_key}: {len(records)} records collected")
        time.sleep(random.uniform(2, 5))  # inter-category cooldown

    df = pd.DataFrame(all_records)

    if df.empty:
        logger.warning("⚠️  No records scraped. Site may be blocking requests.")
        logger.info("💡 Run with Playwright (playwright_scraper.py) for JS-rendered pages.")
    else:
        # Save outputs
        csv_path  = os.path.join(OUTPUT_DIR, "indiamart_raw.csv")
        json_path = os.path.join(OUTPUT_DIR, "indiamart_raw.json")

        df.to_csv(csv_path, index=False)
        df.to_json(json_path, orient="records", indent=2)

        logger.info(f"\n📊 Total records: {len(df)}")
        logger.info(f"💾 CSV  → {csv_path}")
        logger.info(f"💾 JSON → {json_path}")

    return df


if __name__ == "__main__":
    df = run_scraper()
    if not df.empty:
        print(df.head())
