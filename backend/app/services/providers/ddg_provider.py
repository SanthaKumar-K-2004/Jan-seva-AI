"""
Jan-Seva AI — DuckDuckGo Search Provider
Free, no-API-key web search via HTML scraping.
"""

import time
import re
import asyncio
import functools
import requests
from bs4 import BeautifulSoup
from urllib.parse import unquote
from app.utils.logger import logger
from app.services.providers.base import BaseProvider, ProviderResponse, SearchResult


class DuckDuckGoProvider(BaseProvider):
    """DuckDuckGo HTML scraper — free, always available, no API key needed."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

    @property
    def name(self) -> str:
        return "DuckDuckGo"

    def is_available(self) -> bool:
        return True  # No API key needed

    async def search(self, query: str, max_results: int = 5) -> ProviderResponse:
        start = time.monotonic()
        try:
            loop = asyncio.get_running_loop()
            results = await loop.run_in_executor(
                None,
                functools.partial(self._scrape, query, max_results)
            )
            latency = (time.monotonic() - start) * 1000
            logger.info(f"🦆 DuckDuckGo: {len(results)} results in {latency:.0f}ms")
            return ProviderResponse(
                results=results,
                provider_name=self.name,
                latency_ms=latency,
            )
        except Exception as e:
            latency = (time.monotonic() - start) * 1000
            logger.error(f"❌ DuckDuckGo search failed: {e}")
            return ProviderResponse(provider_name=self.name, success=False, error=str(e), latency_ms=latency)

    def _scrape(self, query: str, limit: int) -> list[SearchResult]:
        try:
            url = "https://html.duckduckgo.com/html/"
            res = self.session.post(url, data={"q": query}, timeout=8)
            if res.status_code != 200:
                return []

            soup = BeautifulSoup(res.text, "html.parser")
            results = []
            links = soup.find_all("a", class_="result__a")

            for link in links:
                if len(results) >= limit:
                    break

                title = link.text.strip()
                href = link.get("href", "")
                snippet = ""

                result_div = link.find_parent("div", class_="result__body") or link.find_parent("div", class_="result")
                if result_div:
                    snippet_tag = result_div.find("a", class_="result__snippet")
                    if snippet_tag:
                        snippet = snippet_tag.text.strip()

                # Clean DDG redirect URLs
                if "/l/?" in href:
                    match = re.search(r'uddg=([^&]+)', href)
                    if match:
                        href = unquote(match.group(1))

                if href and title:
                    domain = href.split("/")[2] if len(href.split("/")) > 2 else ""
                    results.append(SearchResult(
                        title=title,
                        url=href,
                        content=snippet,
                        score=0.5,  # Default score for DDG
                        source_name=self.name,
                        domain=domain,
                    ))

            return results
        except Exception as e:
            logger.error(f"DDG scraping error: {e}")
            return []
