"""
Jan-Seva AI — News API Scraper
Uses NewsAPI.org (free tier: 100 req/day) to find scheme-related news.
Searches for government scheme announcements, new launches, budget updates.
Falls back to Google News RSS if no API key configured.
"""

import re
import json
from typing import Optional
from datetime import datetime, timedelta

from app.services.scraper.base_scraper import BaseScraper
from app.utils.logger import logger


class NewsAPIScraper(BaseScraper):
    """
    Scrapes news articles about government schemes using NewsAPI.org
    and Google News RSS as fallback.
    """

    NEWSAPI_URL = "https://newsapi.org/v2/everything"
    GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"

    # Search queries for discovering scheme news
    NEWS_QUERIES = [
        "India government scheme launch 2025",
        "Pradhan Mantri yojana new scheme",
        "Tamil Nadu CM scheme announcement",
        "central government welfare scheme",
        "India subsidy scheme farmers",
        "India scholarship scheme students",
        "PM scheme Rural Development India",
        "health insurance scheme India launch",
        "women empowerment scheme India",
        "India pension yojana update",
    ]

    def __init__(self, api_key: str = ""):
        super().__init__()
        self._api_key = api_key

    async def scrape(self, source: dict) -> dict:
        """Scrape news articles about government schemes."""
        result = {
            "source": "News API",
            "articles_found": 0,
            "schemes_found": 0,
            "status": "started",
        }

        try:
            if self._api_key:
                result = await self._scrape_newsapi(result)
            else:
                result = await self._scrape_google_news_rss(result)

            result["status"] = "success"

        except Exception as e:
            result["status"] = "failed"
            result["error_message"] = str(e)
            logger.error(f"News API scraper failed: {e}")

        self.log_scraper_run("newsapi.org", result["status"], result["schemes_found"])
        return result

    async def _scrape_newsapi(self, result: dict) -> dict:
        """Use NewsAPI.org to find scheme-related news."""
        from_date = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")

        for query in self.NEWS_QUERIES[:5]:  # Limit to conserve free-tier requests
            try:
                response = self.fetch_page(
                    f"{self.NEWSAPI_URL}?"
                    f"q={query.replace(' ', '+')}"
                    f"&from={from_date}"
                    f"&language=en"
                    f"&sortBy=relevancy"
                    f"&pageSize=10"
                    f"&apiKey={self._api_key}",
                    timeout=15,
                )
                data = response.json()

                if data.get("status") != "ok":
                    logger.warning(f"NewsAPI error: {data.get('message', 'Unknown')}")
                    continue

                articles = data.get("articles", [])
                result["articles_found"] += len(articles)

                for article in articles:
                    title = article.get("title", "")
                    desc = article.get("description", "")
                    content = article.get("content", "")
                    url = article.get("url", "")

                    combined = f"{title} {desc} {content}"

                    if self.contains_scheme_keywords(combined):
                        # Store as embedding for RAG
                        embed_text = f"{title}. {desc}. {content}"
                        chunks = self.chunk_text(embed_text)
                        if chunks:
                            self.create_and_store_embeddings(
                                chunks, None, url, f"News: {title[:50]}"
                            )
                            result["schemes_found"] += 1

            except Exception as e:
                logger.warning(f"NewsAPI query failed for '{query}': {e}")

        return result

    async def _scrape_google_news_rss(self, result: dict) -> dict:
        """Fallback: use Google News RSS (no API key needed)."""
        import xml.etree.ElementTree as ET

        for query in self.NEWS_QUERIES:
            try:
                encoded_query = query.replace(" ", "+")
                rss_url = self.GOOGLE_NEWS_RSS.format(query=encoded_query)

                response = self.fetch_page(rss_url, timeout=15)
                root = ET.fromstring(response.text)

                items = root.findall(".//item")
                result["articles_found"] += len(items)

                for item in items[:10]:
                    title_el = item.find("title")
                    link_el = item.find("link")
                    desc_el = item.find("description")

                    title = title_el.text if title_el is not None else ""
                    link = link_el.text if link_el is not None else ""
                    desc = desc_el.text if desc_el is not None else ""

                    # Clean HTML from description
                    desc = re.sub(r"<[^>]+>", "", desc)

                    combined = f"{title} {desc}"

                    if self.contains_scheme_keywords(combined):
                        embed_text = f"{title}. {desc}"
                        chunks = self.chunk_text(embed_text)
                        if chunks:
                            self.create_and_store_embeddings(
                                chunks, None, link, f"Google News: {query[:30]}"
                            )
                            result["schemes_found"] += 1

            except Exception as e:
                logger.warning(f"Google News RSS failed for '{query}': {e}")

        return result


# --- Singleton ---
_news_api_scraper: NewsAPIScraper | None = None


def get_news_api_scraper(api_key: str = "") -> NewsAPIScraper:
    global _news_api_scraper
    if _news_api_scraper is None:
        _news_api_scraper = NewsAPIScraper(api_key)
    return _news_api_scraper
