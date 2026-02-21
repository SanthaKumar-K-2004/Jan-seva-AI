"""
Jan-Seva AI — Tavily Search Provider
AI-optimized search with deep content extraction and images.
"""

import time
import httpx
from app.config import get_settings
from app.utils.logger import logger
from app.services.providers.base import BaseProvider, ProviderResponse, SearchResult


class TavilyProvider(BaseProvider):
    """Tavily AI Search — best for comprehensive, AI-ready search results."""

    BASE_URL = "https://api.tavily.com/search"

    def __init__(self):
        self.api_key = get_settings().tavily_api_key

    @property
    def name(self) -> str:
        return "Tavily"

    def is_available(self) -> bool:
        return bool(self.api_key)

    async def search(self, query: str, max_results: int = 5) -> ProviderResponse:
        if not self.is_available():
            return ProviderResponse(provider_name=self.name, success=False, error="API key missing")

        start = time.monotonic()
        try:
            payload = {
                "api_key": self.api_key,
                "query": query,
                "search_depth": "advanced",
                "include_images": True,
                "include_answer": True,
                "max_results": max_results,
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(self.BASE_URL, json=payload, timeout=30.0)
                response.raise_for_status()
                data = response.json()

            results = []
            for item in data.get("results", []):
                url = item.get("url", "")
                domain = url.split("/")[2] if len(url.split("/")) > 2 else ""
                results.append(SearchResult(
                    title=item.get("title", "Untitled"),
                    url=url,
                    content=item.get("content", ""),
                    score=item.get("score", 0.0),
                    source_name=self.name,
                    published_date=item.get("published_date"),
                    domain=domain,
                ))

            # Parse images
            images = data.get("images", [])
            if images and isinstance(images[0], dict):
                images = [img.get("url") for img in images if img.get("url")]

            latency = (time.monotonic() - start) * 1000
            logger.info(f"🔍 Tavily: {len(results)} results in {latency:.0f}ms")

            return ProviderResponse(
                results=results,
                images=images[:5],
                answer=data.get("answer"),
                provider_name=self.name,
                latency_ms=latency,
            )

        except Exception as e:
            latency = (time.monotonic() - start) * 1000
            logger.error(f"❌ Tavily search failed: {e}")
            return ProviderResponse(provider_name=self.name, success=False, error=str(e), latency_ms=latency)
