"""
Jan-Seva AI - News API Provider
Fetches latest government scheme updates from trusted domains.
"""

import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import httpx

from app.config import get_settings
from app.services.providers.base import BaseProvider, ProviderResponse, SearchResult
from app.utils.logger import logger


class NewsProvider(BaseProvider):
    """News API provider for latest policy announcements and updates."""

    BASE_URL = "https://newsapi.org/v2/everything"

    def __init__(self):
        settings = get_settings()
        self.api_key = settings.news_api_key
        self.allowed_domains = settings.news_allowed_domains
        self.max_news_age_days = settings.max_news_age_days

    @property
    def name(self) -> str:
        return "NewsAPI"

    def is_available(self) -> bool:
        return bool(self.api_key)

    async def search(self, query: str, max_results: int = 5) -> ProviderResponse:
        if not self.is_available():
            return ProviderResponse(provider_name=self.name, success=False, error="API key missing")

        start = time.monotonic()
        try:
            enhanced_query = f"{query} India government scheme"
            from_date = (datetime.now(timezone.utc) - timedelta(days=self.max_news_age_days)).date().isoformat()

            params = {
                "q": enhanced_query,
                "apiKey": self.api_key,
                "language": "en",
                "sortBy": "publishedAt",
                "from": from_date,
                "pageSize": max_results,
            }
            if self.allowed_domains:
                params["domains"] = ",".join(self.allowed_domains)

            async with httpx.AsyncClient() as client:
                response = await client.get(self.BASE_URL, params=params, timeout=15.0)
                response.raise_for_status()
                data = response.json()

            results = []
            for article in data.get("articles", []):
                url = article.get("url", "")
                domain = urlparse(url).netloc.lower() if url else ""
                if self.allowed_domains and not any(allowed in domain for allowed in self.allowed_domains):
                    continue

                description = article.get("description") or ""
                content = article.get("content") or description
                title = article.get("title", "Untitled")
                source_name = article.get("source", {}).get("name", "")

                images = []
                if article.get("urlToImage"):
                    images.append(article["urlToImage"])

                results.append(
                    SearchResult(
                        title=f"{title} - {source_name}" if source_name else title,
                        url=url,
                        content=content[:2000],
                        score=0.65,
                        source_name=self.name,
                        published_date=article.get("publishedAt"),
                        domain=domain,
                        images=images,
                    )
                )

            latency = (time.monotonic() - start) * 1000
            logger.info(
                f"NewsAPI: {len(results)} trusted results in {latency:.0f}ms "
                f"(from>={from_date})"
            )

            all_images = []
            for result in results:
                all_images.extend(result.images)

            return ProviderResponse(
                results=results,
                images=all_images[:3],
                provider_name=self.name,
                latency_ms=latency,
            )
        except Exception as exc:
            latency = (time.monotonic() - start) * 1000
            logger.error(f"NewsAPI search failed: {exc}")
            return ProviderResponse(
                provider_name=self.name,
                success=False,
                error=str(exc),
                latency_ms=latency,
            )
