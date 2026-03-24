"""Base scraper interface for estate agents."""

from abc import ABC, abstractmethod

from models import Property


class BaseScraper(ABC):
    agent_name: str = ""

    @abstractmethod
    async def scrape(self, search_config: dict) -> list[Property]:
        """Scrape listings matching the search config."""
        ...

    @abstractmethod
    async def inspect(self, search_config: dict) -> None:
        """Dump rendered page HTML for debugging selectors."""
        ...
