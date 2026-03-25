"""Foxtons property scraper using Playwright."""

from __future__ import annotations

import asyncio
import re

from playwright.async_api import async_playwright

from models import Property
from scrapers.base import BaseScraper

# Foxtons URL patterns
BASE_URL = "https://www.foxtons.co.uk"
SEARCH_PATH = "/properties-for-sale"


def build_search_url(area: str, search_config: dict) -> str:
    """Build a Foxtons search URL from config."""
    url = f"{BASE_URL}{SEARCH_PATH}/{area}/"
    params = []
    if "min_bedrooms" in search_config:
        params.append(f"bedrooms_from={search_config['min_bedrooms']}")
    if "max_price" in search_config:
        params.append(f"price_to={search_config['max_price']}")
    if "min_price" in search_config:
        params.append(f"price_from={search_config['min_price']}")
    if params:
        url += "?" + "&".join(params)
    return url


class FoxtonsScraper(BaseScraper):
    agent_name = "foxtons"

    async def scrape(self, search_config: dict) -> list[Property]:
        """Scrape Foxtons listings for all configured areas."""
        all_properties = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            for area in search_config.get("areas", []):
                url = build_search_url(area, search_config)
                print(f"  Fetching: {url}")
                props = await self._scrape_page(page, url)
                all_properties.extend(props)
                await asyncio.sleep(2)  # courtesy delay

            await browser.close()

        # Deduplicate across areas (same property could appear in overlapping areas)
        seen_urls = set()
        unique = []
        for prop in all_properties:
            if prop.url not in seen_urls:
                seen_urls.add(prop.url)
                unique.append(prop)

        return unique

    async def _scrape_page(self, page, url: str) -> list[Property]:
        """Scrape a single search results page."""
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        # Wait for property cards to render
        await page.wait_for_timeout(5000)

        properties = []

        # Extract property data from rendered DOM
        # These selectors need to be discovered via inspect command
        cards = await page.query_selector_all('a[href*="/properties-for-sale/"][href*="/chpk"]')
        if not cards:
            # Fallback: try broader selector
            cards = await page.query_selector_all('[data-testid="property-card"], .property-card, [class*="PropertyCard"]')

        for card in cards:
            try:
                prop = await self._parse_card(card, page)
                if prop:
                    properties.append(prop)
            except Exception as e:
                print(f"    Error parsing card: {e}")
                continue

        return properties

    async def _parse_card(self, card, page) -> Property | None:
        """Parse a single property card element into a Property."""
        # Get the link URL
        href = await card.get_attribute("href")
        if not href:
            return None
        url = href if href.startswith("http") else f"{BASE_URL}{href}"

        # Get all text content from the card
        text = await card.inner_text()
        if not text:
            return None

        # Parse price — look for £ followed by numbers
        price_match = re.search(r"£([\d,]+)", text)
        if not price_match:
            return None
        price = int(price_match.group(1).replace(",", ""))

        # Parse address — look for a line containing a comma (street, area, postcode)
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        skip_words = {"recommended", "new", "price reduction", "featured", "under offer"}
        address = "Unknown"
        for line in lines:
            lower = line.lower()
            if lower.startswith("£") or lower in skip_words:
                continue
            if "," in line and any(c.isalpha() for c in line):
                address = line
                break

        # Parse bedrooms
        beds_match = re.search(r"(\d+)\s*bed", text, re.IGNORECASE)
        bedrooms = int(beds_match.group(1)) if beds_match else None

        # Parse bathrooms
        baths_match = re.search(r"(\d+)\s*bath", text, re.IGNORECASE)
        bathrooms = int(baths_match.group(1)) if baths_match else None

        # Try to get image — skip base64 placeholders
        image_url = None
        imgs = await card.query_selector_all("img")
        for img in imgs:
            src = await img.get_attribute("src")
            if src and src.startswith("http") and "assets.foxtons.co.uk" in src:
                image_url = src
                break

        # Parse sq.ft
        sqft_match = re.search(r"([\d,]+)\s*sq\.?ft", text, re.IGNORECASE)
        sqft = sqft_match.group(1) if sqft_match else None

        # Build description from remaining text
        parts = [l for l in lines[:5] if not l.startswith("Calculate")]
        if sqft:
            parts.append(f"{sqft} sq.ft")
        description = " | ".join(parts)

        return Property(
            address=address,
            price=price,
            url=url,
            agent=self.agent_name,
            bedrooms=bedrooms,
            bathrooms=bathrooms,
            image_url=image_url,
            description=description,
        )

    async def inspect(self, search_config: dict) -> None:
        """Dump rendered HTML for first area search — useful for finding selectors."""
        area = search_config.get("areas", ["london"])[0]
        url = build_search_url(area, search_config)
        print(f"Inspecting: {url}")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle")
            await page.wait_for_timeout(5000)

            # Dump page structure
            html = await page.content()
            with open("data/inspect_dump.html", "w") as f:
                f.write(html)
            print(f"Full HTML saved to data/inspect_dump.html ({len(html)} chars)")

            # Try to find property-related elements
            print("\n--- Looking for property cards ---")
            for selector in [
                'a[href*="/properties-for-sale/"]',
                'a[href*="/chpk"]',
                '[data-testid*="property"]',
                '[class*="roperty"]',
                '[class*="listing"]',
                '[class*="card"]',
            ]:
                elements = await page.query_selector_all(selector)
                if elements:
                    print(f"  {selector}: {len(elements)} matches")
                    # Show first match text
                    first_text = await elements[0].inner_text()
                    print(f"    First: {first_text[:200]}")

            await browser.close()
