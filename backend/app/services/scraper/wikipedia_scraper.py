"""
Jan-Seva AI — Wikipedia Scraper
Uses the free Wikipedia API to enrich scheme data with detailed descriptions,
eligibility criteria, history, and external references.
No API key required — uses MediaWiki REST API.
"""

import re
import json
import requests
from typing import Optional
from datetime import datetime

from app.services.scraper.base_scraper import BaseScraper
from app.utils.logger import logger


class WikipediaScraper(BaseScraper):
    """
    Scrapes Wikipedia for government scheme articles.
    Uses the MediaWiki API (free, no key required).
    Flow: Search → Get Article → Extract Sections → Chunk → Embed
    """

    API_URL = "https://en.wikipedia.org/w/api.php"

    # Search queries for discovering schemes
    SEARCH_QUERIES = [
        "Indian government schemes",
        "Pradhan Mantri schemes India",
        "Central government welfare schemes India",
        "Tamil Nadu government schemes",
        "Kerala government schemes",
        "Andhra Pradesh government schemes",
        "Karnataka government schemes",
        "Social welfare schemes India",
        "Education schemes India",
        "Health schemes India government",
        "Agricultural schemes India",
        "Housing schemes India",
        "Employment schemes India",
        "Scholarship schemes India",
        "Pension schemes India",
        "Insurance schemes India government",
        "Women welfare schemes India",
        "SC ST welfare schemes India",
        "MSME schemes India",
        "Rural development schemes India",
    ]

    async def scrape(self, source: dict) -> dict:
        """Scrape Wikipedia for scheme-related articles."""
        result = {
            "source": "Wikipedia",
            "schemes_found": 0,
            "schemes_enriched": 0,
            "status": "started",
        }

        try:
            all_articles = set()

            for query in self.SEARCH_QUERIES:
                articles = self._search_articles(query, limit=20)
                for title in articles:
                    if title not in all_articles:
                        all_articles.add(title)

            logger.info(f"📚 Wikipedia: Found {len(all_articles)} unique articles to process")

            for title in all_articles:
                try:
                    article_data = self._get_article(title)
                    if not article_data:
                        continue

                    content = article_data.get("extract", "")
                    if not content or len(content) < 100:
                        continue

                    # Check if this is scheme-related
                    if not self.contains_scheme_keywords(content):
                        continue

                    # Try to match to existing scheme or create new
                    scheme_name = self._extract_scheme_name_from_title(title)
                    if scheme_name:
                        scheme_id = self._try_match_existing(scheme_name)

                        if scheme_id:
                            # Enrich existing scheme with Wikipedia data
                            self._enrich_scheme(scheme_id, article_data)
                            result["schemes_enriched"] += 1
                        else:
                            # Create new scheme from Wikipedia
                            scheme_data = self._parse_article_to_scheme(article_data)
                            if scheme_data:
                                new_id = self.upsert_scheme(scheme_data)
                                if new_id:
                                    # Create embeddings
                                    embed_text = f"{scheme_data['name']}. {scheme_data.get('description', '')}"
                                    chunks = self.chunk_text(embed_text)
                                    self.create_and_store_embeddings(
                                        chunks, new_id,
                                        f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
                                        "Wikipedia"
                                    )
                                    result["schemes_found"] += 1

                except Exception as e:
                    logger.warning(f"Failed to process Wikipedia article '{title}': {e}")

            result["status"] = "success"

        except Exception as e:
            result["status"] = "failed"
            result["error_message"] = str(e)
            logger.error(f"Wikipedia scraper failed: {e}")

        self.log_scraper_run("wikipedia.org", result["status"], result["schemes_found"])
        return result

    def _search_articles(self, query: str, limit: int = 20) -> list[str]:
        """Search Wikipedia for articles matching a query."""
        try:
            params = {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": limit,
                "format": "json",
                "utf8": 1,
            }
            response = self.fetch_page(f"{self.API_URL}?{'&'.join(f'{k}={v}' for k, v in params.items())}")
            data = response.json()
            return [item["title"] for item in data.get("query", {}).get("search", [])]
        except Exception as e:
            logger.warning(f"Wikipedia search failed for '{query}': {e}")
            return []

    def _get_article(self, title: str) -> Optional[dict]:
        """Get full article content from Wikipedia."""
        try:
            params = {
                "action": "query",
                "titles": title.replace(" ", "+"),
                "prop": "extracts|info|categories",
                "exintro": "false",
                "explaintext": "true",
                "exlimit": 1,
                "inprop": "url",
                "format": "json",
                "utf8": 1,
            }
            url = f"{self.API_URL}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
            response = self.fetch_page(url)
            data = response.json()

            pages = data.get("query", {}).get("pages", {})
            for page_id, page_data in pages.items():
                if page_id == "-1":
                    return None
                return {
                    "title": page_data.get("title", ""),
                    "extract": page_data.get("extract", ""),
                    "url": page_data.get("fullurl", ""),
                    "categories": [
                        c.get("title", "").replace("Category:", "")
                        for c in page_data.get("categories", [])
                    ],
                }

        except Exception as e:
            logger.warning(f"Failed to get Wikipedia article '{title}': {e}")
            return None

    def _extract_scheme_name_from_title(self, title: str) -> Optional[str]:
        """Extract scheme name from Wikipedia article title."""
        # Remove disambiguation
        name = re.sub(r"\s*\(.*?\)\s*$", "", title).strip()
        if len(name) < 5:
            return None
        return name

    def _try_match_existing(self, scheme_name: str) -> Optional[str]:
        """Try to match a scheme name to an existing scheme in DB."""
        slug = self.generate_slug(scheme_name)
        try:
            result = self._client.table("schemes").select("id").eq("slug", slug).execute()
            if result.data:
                return result.data[0]["id"]
        except Exception:
            pass
        return None

    def _enrich_scheme(self, scheme_id: str, article_data: dict):
        """Enrich an existing scheme with Wikipedia data."""
        try:
            extract = article_data.get("extract", "")
            if not extract:
                return

            # Add Wikipedia content as additional embeddings
            chunks = self.chunk_text(extract)
            if chunks:
                self.create_and_store_embeddings(
                    chunks, scheme_id,
                    article_data.get("url", ""),
                    "Wikipedia"
                )

            # Update the description if current one is short
            existing = (
                self._client.table("schemes")
                .select("description")
                .eq("id", scheme_id)
                .execute()
            )
            if existing.data:
                current_desc = existing.data[0].get("description", "")
                if len(current_desc) < len(extract) // 2:
                    # Wikipedia has better description
                    wiki_desc = extract[:2000]
                    self._client.table("schemes").update({
                        "description": wiki_desc,
                    }).eq("id", scheme_id).execute()

        except Exception as e:
            logger.warning(f"Failed to enrich scheme {scheme_id}: {e}")

    def _parse_article_to_scheme(self, article_data: dict) -> Optional[dict]:
        """Parse Wikipedia article into scheme data format."""
        title = article_data.get("title", "")
        extract = article_data.get("extract", "")

        if not title or not extract:
            return None

        # Detect state from content
        state = "Central"
        lower_extract = extract.lower()
        if "tamil nadu" in lower_extract:
            state = "Tamil Nadu"
        elif "kerala" in lower_extract:
            state = "Kerala"
        elif "andhra pradesh" in lower_extract:
            state = "Andhra Pradesh"
        elif "karnataka" in lower_extract:
            state = "Karnataka"
        elif "maharashtra" in lower_extract:
            state = "Maharashtra"
        elif "uttar pradesh" in lower_extract:
            state = "Uttar Pradesh"
        elif "rajasthan" in lower_extract:
            state = "Rajasthan"

        # Detect category
        categories = []
        cats = article_data.get("categories", [])
        cat_text = " ".join(cats).lower()
        if any(w in cat_text for w in ["agriculture", "farming", "rural"]):
            categories.append("Agriculture")
        if any(w in cat_text for w in ["education", "scholarship", "school"]):
            categories.append("Education")
        if any(w in cat_text for w in ["health", "medical", "hospital"]):
            categories.append("Health")
        if any(w in cat_text for w in ["housing", "shelter", "home"]):
            categories.append("Housing")
        if any(w in cat_text for w in ["women", "gender", "maternal"]):
            categories.append("Women")
        if any(w in cat_text for w in ["employment", "labour", "skill"]):
            categories.append("Employment")
        if not categories:
            categories = ["Government Scheme"]

        # Extract benefits from text
        benefits = ""
        benefit_phrases = re.findall(
            r"(?:provides?|offers?|gives?|benefits?\s+include)\s+(.+?)(?:\.|$)",
            extract[:1000], re.IGNORECASE
        )
        if benefit_phrases:
            benefits = benefit_phrases[0][:300]

        return {
            "name": title,
            "slug": self.generate_slug(title),
            "description": extract[:2000],
            "state": state,
            "category": categories,
            "benefits": benefits,
            "source_url": article_data.get("url", ""),
            "source_type": "wikipedia",
            "ministry": "",
        }


# --- Singleton ---
_wikipedia_scraper: WikipediaScraper | None = None


def get_wikipedia_scraper() -> WikipediaScraper:
    global _wikipedia_scraper
    if _wikipedia_scraper is None:
        _wikipedia_scraper = WikipediaScraper()
    return _wikipedia_scraper
