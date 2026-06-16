"""
Playwright-Based TradeIndia Scraper
====================================
TradeIndia loads content via JavaScript, so requires Playwright.
Use this instead of tradeindia_scraper.py for reliable data extraction.

Usage:
    python src/tradeindia_playwright_scraper.py
"""

import asyncio
import json
import os
import random
import logging
import re
import pandas as pd
from datetime import datetime
from playwright.async_api import async_playwright, Page, BrowserContext

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

CATEGORIES = {
    "industrial_machinery": "industrial machinery",
    "electronics":          "electronics components",
    "textiles":             "textile fabric",
    "chemicals":            "industrial chemicals",
    "agriculture":          "agricultural equipment",
}

SEARCH_URL = "https://www.tradeindia.com/search.html?q={query}&page={page}"
PAGES_PER_CAT = 6


async def human_delay(min_s=1.5, max_s=4.0):
    """Randomized delay to mimic human browsing."""
    await asyncio.sleep(random.uniform(min_s, max_s))


async def setup_browser(playwright) -> tuple:
    """Launch browser with stealth settings."""
    browser = await playwright.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
        ]
    )
    context: BrowserContext = await browser.new_context(
        viewport={"width": 1366, "height": 768},
        user_agent=random.choice([
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
        ]),
        locale="en-IN",
        timezone_id="Asia/Kolkata",
        extra_http_headers={
            "Accept-Language": "en-IN,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
        }
    )
    # Bypass webdriver detection
    await context.add_init_script("""Object.defineProperty(navigator, 'webdriver', {get: () => undefined})""")
    # Block images/fonts to speed up
    await context.route("**/*.{png,jpg,jpeg,gif,svg,woff,woff2,ttf}", lambda r: r.abort())
    return browser, context


def parse_price(price_text: str) -> dict:
    """Parse price from text."""
    if not price_text:
        return {"price_min": None, "price_max": None, "unit": None}

    price_text = price_text.strip()
    numbers = re.findall(r"[\d,]+(?:\.\d+)?", price_text.replace(",", ""))
    numbers = [float(n.replace(",", "")) for n in numbers if n]

    unit_match = re.search(r"/\s*([A-Za-z\s]+)", price_text)
    unit = unit_match.group(1).strip() if unit_match else "Unit"

    return {
        "price_min": numbers[0] if numbers else None,
        "price_max": numbers[1] if len(numbers) > 1 else numbers[0] if numbers else None,
        "unit": unit,
    }


async def extract_products_from_page(page: Page, category: str) -> list[dict]:
    """Extract products from TradeIndia page."""
    products = []

    try:
        await page.wait_for_selector("body", timeout=15000)
        await human_delay(1.5, 2.5)

        # TradeIndia product selectors - try multiple strategies
        selectors = [
            "div[data-testid*='product']",
            "div.product-item",
            "div.item-box",
            "a[href*='/products/']",
            "div.search-item",
        ]

        cards = []
        for sel in selectors:
            try:
                cards = await page.query_selector_all(sel)
                if len(cards) > 0:
                    logger.info(f"  Found {len(cards)} cards with selector: {sel}")
                    break
            except:
                continue

        logger.info(f"  Extracting from {len(cards)} product cards")

        for card in cards:
            try:
                # Extract text from card
                card_text = await card.inner_text()
                if not card_text or len(card_text) < 5:
                    continue

                # Get all text elements
                texts = card_text.split("\n")
                texts = [t.strip() for t in texts if t.strip()]

                if len(texts) < 2:
                    continue

                product_name = texts[0]
                location = "Unknown"
                price_raw = None
                rating_raw = None

                # Parse remaining text for location, price, rating
                for text in texts[1:]:
                    if any(x in text.lower() for x in ["delhi", "mumbai", "pune", "bengaluru", "state", "city"]):
                        location = text
                    elif any(x in text for x in ["Rs", "₹", "$", "/", "price"]):
                        price_raw = text
                    elif any(x in text for x in ["rating", "star", "review", "4.", "5."]):
                        rating_raw = text

                # Try to extract rating
                rating = None
                if rating_raw:
                    nums = re.findall(r"\d+\.?\d*", rating_raw)
                    if nums:
                        rating = float(nums[0])

                # Extract link
                link_el = await card.query_selector("a")
                product_url = None
                if link_el:
                    href = await link_el.get_attribute("href")
                    if href:
                        product_url = f"https://www.tradeindia.com{href}" if href.startswith("/") else href

                price_data = parse_price(price_raw or "")

                product = {
                    "product_name": product_name,
                    "supplier_name": "Unknown",  # Not always available
                    "location": location,
                    "category": category,
                    "price_min": price_data["price_min"],
                    "price_max": price_data["price_max"],
                    "price_unit": price_data["unit"],
                    "currency": "INR",
                    "rating": rating,
                    "moq": None,
                    "verified": False,
                    "product_url": product_url,
                    "scraped_at": datetime.utcnow().isoformat(),
                }

                if product["product_name"]:
                    products.append(product)

            except Exception as e:
                logger.debug(f"Card extraction error: {e}")
                continue

    except Exception as e:
        logger.error(f"Page extraction error: {e}")

    return products


async def scrape_category_tradeindia(context, category_key: str, search_term: str) -> list[dict]:
    """Scrape TradeIndia category."""
    all_products = []
    page = await context.new_page()

    try:
        for page_num in range(1, PAGES_PER_CAT + 1):
            url = SEARCH_URL.format(query=search_term.replace(" ", "+"), page=page_num)
            logger.info(f"  [{category_key}] Page {page_num}: {url}")

            try:
                response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)

                if response and response.status == 200:
                    products = await extract_products_from_page(page, category_key)
                    all_products.extend(products)
                    logger.info(f"  ✓ Page {page_num}: {len(products)} products")
                else:
                    logger.warning(f"  ⚠ Page {page_num}: status {response.status if response else 'N/A'}")

            except Exception as e:
                logger.warning(f"  Page load error: {e}")

            await human_delay(2, 4)

    finally:
        await page.close()

    return all_products


async def run_tradeindia_scraper():
    """Main TradeIndia scraping pipeline."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    all_records = []

    async with async_playwright() as pw:
        browser, context = await setup_browser(pw)

        try:
            for cat_key, search_term in CATEGORIES.items():
                logger.info(f"\n📦 Scraping TradeIndia: {cat_key}")
                records = await scrape_category_tradeindia(context, cat_key, search_term)
                all_records.extend(records)
                logger.info(f"✓ {cat_key}: {len(records)} records")
                await human_delay(3, 6)

        finally:
            await context.close()
            await browser.close()

    # Save data
    df = pd.DataFrame(all_records)
    if not df.empty:
        df.to_csv(os.path.join(OUTPUT_DIR, "tradeindia_raw.csv"), index=False)
        df.to_json(os.path.join(OUTPUT_DIR, "tradeindia_raw.json"), orient="records", indent=2)
        logger.info(f"\n{'='*70}")
        logger.info(f"Total TradeIndia records: {len(df)}")
        logger.info(f"{'='*70}")
    else:
        logger.warning("No records collected from TradeIndia")

    return df


if __name__ == "__main__":
    asyncio.run(run_tradeindia_scraper())
