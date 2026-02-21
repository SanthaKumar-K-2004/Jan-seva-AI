"""
Jan-Seva AI — Wikipedia Search Provider
Searches Wikipedia for scheme/policy background knowledge.
"""

import time
import httpx
from app.config import get_settings
from app.utils.logger import logger
from app.services.providers.base import BaseProvider, ProviderResponse, SearchResult


class WikipediaProvider(BaseProvider):
    """Wikipedia API — excellent for background knowledge on government programs."""

    API_URL = "https://en.wikipedia.org/w/api.php"

    def __init__(self):
        settings = get_settings()
        self.access_token = settings.wikipedia_access_token

    @property
    def name(self) -> str:
        return "Wikipedia"

    def is_available(self) -> bool:
        return True  # Wikipedia API works without auth too

    async def search(self, query: str, max_results: int = 3) -> ProviderResponse:
        start = time.monotonic()
        try:
            params = {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": max_results,
                "srprop": "snippet|timestamp",
                "format": "json",
                "origin": "*",
            }

            headers = {}
            if self.access_token:
                headers["Authorization"] = f"Bearer {self.access_token}"
            headers["User-Agent"] = "JanSevaAI/1.0 (https://jan-seva.ai; contact@jan-seva.ai)"

            async with httpx.AsyncClient() as client:
                response = await client.get(self.API_URL, params=params, headers=headers, timeout=10.0)
                response.raise_for_status()
                data = response.json()

            results = []
            for item in data.get("query", {}).get("search", []):
                title = item.get("title", "")
                # Clean HTML from snippet
                snippet = item.get("snippet", "")
                snippet = snippet.replace('<span class="searchmatch">', "").replace("</span>", "")

                url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"

                results.append(SearchResult(
                    title=title,
                    url=url,
                    content=snippet,
                    score=0.7,  # Wikipedia is generally reliable
                    source_name=self.name,
                    published_date=item.get("timestamp"),
                    domain="en.wikipedia.org",
                ))

            # Fetch full extracts for top results
            if results:
                results = await self._enrich_extracts(results, headers)

            latency = (time.monotonic() - start) * 1000
            logger.info(f"📚 Wikipedia: {len(results)} results in {latency:.0f}ms")
            return ProviderResponse(
                results=results,
                provider_name=self.name,
                latency_ms=latency,
            )

        except Exception as e:
            latency = (time.monotonic() - start) * 1000
            logger.error(f"❌ Wikipedia search failed: {e}")
            return ProviderResponse(provider_name=self.name, success=False, error=str(e), latency_ms=latency)

    async def _enrich_extracts(self, results: list[SearchResult], headers: dict) -> list[SearchResult]:
        """Fetch full text extracts for search results."""
        try:
            titles = "|".join([r.title for r in results[:3]])
            params = {
                "action": "query",
                "titles": titles,
                "prop": "extracts",
                "exintro": True,
                "explaintext": True,
                "format": "json",
                "origin": "*",
            }

            async with httpx.AsyncClient() as client:
                response = await client.get(self.API_URL, params=params, headers=headers, timeout=10.0)
                response.raise_for_status()
                data = response.json()

            pages = data.get("query", {}).get("pages", {})
            extract_map = {}
            for page in pages.values():
                title = page.get("title", "")
                extract = page.get("extract", "")
                if title and extract:
                    extract_map[title] = extract[:2000]

            for result in results:
                if result.title in extract_map:
                    result.content = extract_map[result.title]

            return results
        except Exception:
            return results  # Return original results if enrichment fails
