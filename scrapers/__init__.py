"""Scraper registry — maps agent names to scraper classes."""

from scrapers.foxtons import FoxtonsScraper

AGENT_REGISTRY = {
    "foxtons": FoxtonsScraper,
}
