"""
Playwright-Based IndiaMART Scraper
=====================================
Use this when the requests-based scraper gets blocked (403/429).
Playwright renders JavaScript, handles dynamic content, and 
mimics real browser behaviour more convincingly.

Usage:
    python src/playwright_scraper.py

Requirements:
    pip install playwright
    playwright install chromium
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

SEARCH_URL = "https://dir.indiamart.com/search.mp?ss={query}&page={page}"
PAGES_PER_CAT = 13


async def human_delay(min_s=1.0, max_s=3.0):
    """Randomised delay to mimic human browsing speed."""
    await asyncio.sleep(random.uniform(min_s, max_s))


async def setup_browser(playwright) -> tuple:
    """Launch browser with stealth-like settings."""
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
    # Bypass webdriver detection (Cloudflare bot detection)
    await context.add_init_script("""Object.defineProperty(navigator, 'webdriver', {get: () => undefined})""")
    # Block images and fonts to speed up scraping
    await context.route("**/*.{png,jpg,jpeg,gif,svg,woff,woff2,ttf}", lambda r: r.abort())
    return browser, context


async def extract_products_from_page(page: Page, category: str) -> list[dict]:
    """Extract product data from current page using multiple selector strategies."""
    products = []

    try:
        # Wait for content to load
        await page.wait_for_selector("body", timeout=10000)
        await human_delay(1, 2)

        # Get all product containers — IndiaMART uses staticListingCard
        selectors = [
            ".staticListingCard",
            ".product-card",
            ".lst-card",
            "[data-name]",
            ".prd-item",
            "section.staticListingCard",
        ]

        cards = []
        for sel in selectors:
            cards = await page.query_selector_all(sel)
            if cards:
                logger.info(f"  Found {len(cards)} cards with selector: {sel}")
                break

        for card in cards:
            try:
                # IndiaMART specific selectors
                name    = await card.query_selector("h2, .prd-name, .product-title")
                company = await card.query_selector(".company-name, .supplier-name, .staticMetaLine")
                loc     = await card.query_selector(".location, .city-name, .staticMetaLineShort")
                price   = await card.query_selector(".price, .cost, [data-price]")
                rating  = await card.query_selector(".rating, .star-rating, [data-rating]")
                link    = await card.query_selector("a[href]")

                product = {
                    "product_name":  await name.inner_text()    if name    else None,
                    "supplier_name": await company.inner_text() if company else "Unknown",
                    "location":      await loc.inner_text()     if loc     else "Unknown",
                    "category":      category,
                    "price_raw":     await price.inner_text()   if price   else None,
                    "rating_raw":    await rating.inner_text()  if rating  else None,
                    "product_url":   await link.get_attribute("href") if link else None,
                    "scraped_at":    datetime.utcnow().isoformat(),
                }

                if product["product_name"]:
                    products.append(product)

            except Exception as e:
                logger.debug(f"Card extraction error: {e}")
                continue

    except Exception as e:
        logger.error(f"Page extraction error: {e}")

    return products


async def scrape_category_playwright(context, category_key: str, search_term: str) -> list[dict]:
    """Scrape all pages for a category using Playwright."""
    all_products = []
    page = await context.new_page()

    try:
        for page_num in range(1, PAGES_PER_CAT + 1):
            url = SEARCH_URL.format(query=search_term.replace(" ", "+"), page=page_num)
            logger.info(f"  [{category_key}] Page {page_num}: {url}")

            response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)

            if response and response.status == 200:
                products = await extract_products_from_page(page, category_key)
                all_products.extend(products)
                logger.info(f"  ✅ Page {page_num}: {len(products)} products")
            else:
                status = response.status if response else "N/A"
                logger.warning(f"  ⚠️  Page {page_num}: status {status}")

            await human_delay(2, 4)

    finally:
        await page.close()

    return all_products


async def run_playwright_scraper():
    """Main async scraping pipeline."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    all_records = []

    async with async_playwright() as pw:
        browser, context = await setup_browser(pw)

        try:
            for cat_key, search_term in CATEGORIES.items():
                logger.info(f"\n📦 Scraping: {cat_key}")
                records = await scrape_category_playwright(context, cat_key, search_term)
                all_records.extend(records)
                logger.info(f"✅ {cat_key}: {len(records)} total records")
                await human_delay(3, 6)

        finally:
            await context.close()
            await browser.close()

    df = pd.DataFrame(all_records)
    if not df.empty:
        df.to_csv(os.path.join(OUTPUT_DIR, "indiamart_raw.csv"), index=False)
        df.to_json(os.path.join(OUTPUT_DIR, "indiamart_raw.json"), orient="records", indent=2)
        logger.info(f"\n📊 Total scraped: {len(df)} records across {df['category'].nunique()} categories")
    else:
        logger.warning("No records collected — check logs for errors")

    return df


if __name__ == "__main__":
    asyncio.run(run_playwright_scraper())
