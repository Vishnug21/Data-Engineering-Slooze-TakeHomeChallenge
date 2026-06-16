"""
TradeIndia B2B Marketplace Scraper
===================================
Scrapes product listings across multiple categories:
  - Industrial Machinery
  - Electronics & Electrical
  - Textiles & Apparel
  - Chemicals & Fertilizers
  - Agriculture & Equipment

Anti-bot Detection Measures:
  - Rotating User-Agent headers (8 variants)
  - Randomized request delays (1.5-4s per request, 3-6s between categories)
  - Session-based requests with persistent cookies
  - Retry logic with exponential backoff
  - robots.txt compliance checks
  - Realistic HTTP headers (Accept, Accept-Language, Referer, DNT)
  - Request timeout handling with fallback
  - Browser-like headers (Sec-Fetch-*, Sec-Ch-Ua)

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
        logging.FileHandler("tradeindia_scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
BASE_URL = "https://www.tradeindia.com/search.html"

CATEGORIES = {
    "industrial_machinery": "industrial machinery",
    "electronics":          "electronics components",
    "textiles":             "textile fabric",
    "chemicals":            "industrial chemicals",
    "agriculture":          "agricultural equipment",
}

# Extended user agents pool (8 variants for better rotation)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",
]

# Realistic referers
REFERERS = [
    "https://www.google.com/",
    "https://www.google.co.in/",
    "https://www.bing.com/",
    "https://duckduckgo.com/",
    "https://www.tradeindia.com/",
]

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
PAGES_PER_CATEGORY = 6
DELAY_MIN = 1.5
DELAY_MAX = 4.0
DELAY_BETWEEN_CATEGORIES_MIN = 3.0
DELAY_BETWEEN_CATEGORIES_MAX = 6.0
MAX_RETRIES = 4


# ── Robots.txt compliance ─────────────────────────────────────────────────────
def can_fetch(url: str) -> bool:
    """Check robots.txt before scraping."""
    try:
        rp = RobotFileParser()
        robots_url = "https://www.tradeindia.com/robots.txt"
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch("*", url)
    except Exception as e:
        logger.debug(f"robots.txt check failed: {e}")
        return True  # Fail open if robots.txt unreachable


# ── HTTP helpers ──────────────────────────────────────────────────────────────
def make_session() -> requests.Session:
    """Create a requests session with realistic headers."""
    session = requests.Session()

    # Randomized realistic headers
    session.headers.update({
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": random.choice([
            "en-IN,en;q=0.9,hi;q=0.8",
            "en-US,en;q=0.9",
            "en;q=0.9",
        ]),
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Referer": random.choice(REFERERS),
        "DNT": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Sec-Ch-Ua": '"Not A(Brand";v="99", "Google Chrome";v="124", "Chromium";v="124"',
        "Sec-Ch-Ua-Mobile": "?0",
    })
    return session


def fetch_page(session: requests.Session, url: str, retries: int = MAX_RETRIES) -> Optional[str]:
    """Fetch a page with retry + exponential backoff + anti-bot measures."""
    for attempt in range(retries):
        try:
            # Random delay to appear human-like
            delay = random.uniform(DELAY_MIN, DELAY_MAX)
            time.sleep(delay)

            # Rotate user agent and referer on each attempt
            session.headers["User-Agent"] = random.choice(USER_AGENTS)
            session.headers["Referer"] = random.choice(REFERERS)

            # Make request with timeout
            response = session.get(url, timeout=25)
            response.raise_for_status()

            logger.info(f"✅ [{response.status_code}] {url}")
            return response.text

        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code

            if status_code == 403:
                logger.warning(f"⚠️  403 Forbidden on attempt {attempt+1} — backing off")
                time.sleep(2 ** attempt * 3)  # Exponential backoff: 3s, 6s, 12s, 24s

            elif status_code == 429:
                logger.warning(f"⚠️  429 Rate Limited — sleeping 45s")
                time.sleep(45)

            elif status_code in [503, 502]:
                logger.warning(f"⚠️  {status_code} Service Unavailable — sleeping 30s")
                time.sleep(30)

            else:
                logger.error(f"HTTP {status_code}: {e}")
                if attempt == retries - 1:
                    break
                time.sleep(2 ** attempt)

        except requests.exceptions.Timeout:
            logger.warning(f"⏱️  Timeout on attempt {attempt+1} — retrying")
            time.sleep(2 ** attempt * 2)

        except requests.exceptions.ConnectionError as e:
            logger.warning(f"🔌 Connection error on attempt {attempt+1}: {e}")
            time.sleep(2 ** attempt * 2)

        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed (attempt {attempt+1}): {e}")
            if attempt == retries - 1:
                break
            time.sleep(2 ** attempt)

    logger.error(f"❌ Failed to fetch after {retries} retries: {url}")
    return None


# ── Parsers ───────────────────────────────────────────────────────────────────
def parse_price(price_text: str) -> dict:
    """Normalize price strings like 'Rs 500 - Rs 1,000 / Piece' into structured dict."""
    if not price_text:
        return {"price_min": None, "price_max": None, "unit": None, "currency": "INR"}

    price_text = price_text.strip()

    # Detect currency
    if "Rs" in price_text or "₹" in price_text:
        currency = "INR"
    elif "$" in price_text:
        currency = "USD"
    else:
        currency = "INR"

    # Extract numbers (handle commas)
    numbers = re.findall(r"[\d,]+(?:\.\d+)?", price_text.replace(",", ""))
    numbers = [float(n.replace(",", "")) for n in numbers if n]

    # Extract unit (everything after '/')
    unit_match = re.search(r"/\s*([A-Za-z\s]+)(?:\s|$)", price_text)
    unit = unit_match.group(1).strip() if unit_match else "Unit"

    return {
        "price_min": numbers[0] if numbers else None,
        "price_max": numbers[1] if len(numbers) > 1 else numbers[0] if numbers else None,
        "unit": unit,
        "currency": currency,
    }


def parse_product_card(card, category: str) -> Optional[dict]:
    """Extract structured data from a TradeIndia product listing card."""
    try:
        # Product name - try multiple selectors
        name_el = (
            card.find("h3") or
            card.find("h2") or
            card.find(class_=re.compile(r"title|name|product", re.I))
        )
        product_name = name_el.get_text(strip=True) if name_el else None
        if not product_name or len(product_name) < 3:
            return None

        # Supplier/Company name
        supplier_el = card.find(class_=re.compile(r"company|supplier|seller|org", re.I))
        supplier_name = supplier_el.get_text(strip=True) if supplier_el else "Unknown"

        # Location (city, state)
        loc_el = card.find(class_=re.compile(r"location|city|place|address", re.I))
        location = loc_el.get_text(strip=True) if loc_el else "Unknown"

        # Price
        price_el = card.find(class_=re.compile(r"price|cost|rate|amount", re.I))
        price_raw = price_el.get_text(strip=True) if price_el else ""
        price_data = parse_price(price_raw)

        # Rating
        rating_el = card.find(class_=re.compile(r"rating|star|review", re.I))
        rating_text = rating_el.get_text(strip=True) if rating_el else ""
        rating_nums = re.findall(r"\d+\.?\d*", rating_text)
        rating = float(rating_nums[0]) if rating_nums else None

        # MOQ (Minimum Order Quantity)
        moq_text = card.get_text(strip=True)
        moq_match = re.search(r"(?:min.*?order|moq|m\.o\.q)[:\s]*(\d+\s*(?:piece|kg|meter|unit)?)", moq_text, re.I)
        moq = moq_match.group(1).strip() if moq_match else None

        # Product URL
        link_el = card.find("a", href=True)
        product_url = None
        if link_el and link_el.get("href"):
            href = link_el["href"]
            product_url = urljoin("https://www.tradeindia.com", href)

        # Verified supplier badge
        verified = bool(card.find(class_=re.compile(r"verified|trust|certified", re.I)))

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
    """Scrape multiple pages for a single category on TradeIndia."""
    results = []
    logger.info(f"\n📦 Scraping TradeIndia category: {category_key}")

    for page in range(1, PAGES_PER_CATEGORY + 1):
        # TradeIndia search URL pattern
        params = {"q": search_term, "page": page}
        url = f"{BASE_URL}?{urlencode(params)}"

        # Check robots.txt
        if not can_fetch(url):
            logger.warning(f"robots.txt disallows: {url}")
            continue

        # Fetch page
        html = fetch_page(session, url)
        if not html:
            logger.warning(f"Skipping page {page} — no content returned")
            continue

        # Parse HTML
        soup = BeautifulSoup(html, "html.parser")

        # Try multiple product card selectors (TradeIndia structure)
        cards = (
            soup.find_all("div", class_=re.compile(r"product|listing|item|card", re.I)) or
            soup.find_all("li", class_=re.compile(r"product|item", re.I)) or
            soup.find_all("div", attrs={"data-product-id": True})
        )

        logger.info(f"  Page {page}: found {len(cards)} product cards")

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

    logger.info("=" * 70)
    logger.info("🚀 Starting TradeIndia B2B Marketplace Scraper")
    logger.info("=" * 70)
    logger.info(f"Base URL: {BASE_URL}")
    logger.info(f"Categories: {list(CATEGORIES.keys())}")
    logger.info(f"Pages per category: {PAGES_PER_CATEGORY}")
    logger.info(f"Request delay: {DELAY_MIN}–{DELAY_MAX}s")
    logger.info(f"Category cooldown: {DELAY_BETWEEN_CATEGORIES_MIN}–{DELAY_BETWEEN_CATEGORIES_MAX}s")
    logger.info("=" * 70)

    for idx, (cat_key, search_term) in enumerate(CATEGORIES.items()):
        records = scrape_category(session, cat_key, search_term)
        all_records.extend(records)
        logger.info(f"✅ {cat_key}: {len(records)} records collected")

        # Inter-category cooldown (except after last category)
        if idx < len(CATEGORIES) - 1:
            cooldown = random.uniform(DELAY_BETWEEN_CATEGORIES_MIN, DELAY_BETWEEN_CATEGORIES_MAX)
            logger.info(f"⏳ Cooling down {cooldown:.1f}s before next category...")
            time.sleep(cooldown)

    # Create DataFrame
    df = pd.DataFrame(all_records)

    if df.empty:
        logger.warning("⚠️  No records scraped. Website may be blocking requests.")
        logger.info("💡 Possible solutions:")
        logger.info("   - Check if TradeIndia's structure changed")
        logger.info("   - Try Playwright scraper for JavaScript-rendered pages")
        logger.info("   - Verify robots.txt allows scraping")
    else:
        # Save outputs
        csv_path = os.path.join(OUTPUT_DIR, "tradeindia_raw.csv")
        json_path = os.path.join(OUTPUT_DIR, "tradeindia_raw.json")

        df.to_csv(csv_path, index=False)
        df.to_json(json_path, orient="records", indent=2)

        logger.info("\n" + "=" * 70)
        logger.info(f"📊 Total records scraped: {len(df)}")
        logger.info(f"💾 CSV  → {csv_path}")
        logger.info(f"💾 JSON → {json_path}")
        logger.info("=" * 70)

    return df


if __name__ == "__main__":
    df = run_scraper()
    if not df.empty:
        print("\n✅ Sample of scraped data:")
        print(df.head(10))
        print(f"\n📊 Shape: {df.shape}")
        print(f"\n🏷️  Categories distribution:")
        print(df["category"].value_counts())
