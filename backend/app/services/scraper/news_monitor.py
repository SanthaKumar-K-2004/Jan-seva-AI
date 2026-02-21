"""
Jan-Seva AI — News Monitor
Monitors government news RSS feeds (PIB, DD News) for scheme announcements.
Filters by keywords, extracts scheme info, stores embeddings for RAG context.
"""

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Optional

from app.services.scraper.base_scraper import BaseScraper
from app.utils.logger import logger


class NewsMonitor(BaseScraper):
    """
    RSS/Atom feed monitor for government news sources.
    Watches PIB, DD News, and other feeds for scheme-related updates.
    """

    # RSS feed URLs — comprehensive government news sources
    RSS_FEEDS = [
        {"name": "PIB Press Releases", "url": "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3", "type": "rss"},
        {"name": "PIB PM Office", "url": "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=26", "type": "rss"},
        {"name": "DD News Feed", "url": "https://ddnews.gov.in/en/feed/", "type": "rss"},
        {"name": "India.gov.in Updates", "url": "https://www.india.gov.in/rss/all-whats-new/feed/en", "type": "rss"},
        {"name": "PIB Agriculture Ministry", "url": "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=40", "type": "rss"},
        {"name": "PIB Finance Ministry", "url": "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=27", "type": "rss"},
        {"name": "PIB Rural Development", "url": "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=41", "type": "rss"},
        {"name": "PIB Health Ministry", "url": "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=31", "type": "rss"},
        {"name": "PIB Education Ministry", "url": "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=34", "type": "rss"},
        {"name": "PIB Social Justice", "url": "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=55", "type": "rss"},
    ]

    async def scrape(self, source: dict) -> dict:
        """Monitor a single RSS feed for scheme-related news."""
        result = {"source": source["name"], "schemes_found": 0, "status": "started"}

        try:
            response = self.fetch_page(source["url"])
            entries = self._parse_feed(response.text)

            # Filter for scheme-related entries from last 24 hours
            cutoff = datetime.utcnow() - timedelta(hours=24)
            scheme_entries = []

            for entry in entries:
                title = entry.get("title", "")
                desc = entry.get("description", "")
                combined = f"{title} {desc}"

                if self.contains_scheme_keywords(combined):
                    pub_date = entry.get("pub_date")
                    if pub_date and pub_date > cutoff:
                        scheme_entries.append(entry)
                    elif not pub_date:
                        # No date? Include it anyway
                        scheme_entries.append(entry)

            # Process scheme-related entries
            for entry in scheme_entries[:20]:  # Limit per feed
                try:
                    embed_text = f"{entry['title']}. {entry.get('description', '')}"
                    chunks = self.chunk_text(embed_text)

                    if chunks:
                        self.create_and_store_embeddings(
                            chunks,
                            scheme_id=None,
                            source_url=entry.get("link", source["url"]),
                            source_name=f"News: {source['name']}",
                        )
                        result["schemes_found"] += 1

                except Exception as e:
                    logger.warning(f"Failed to process news entry: {e}")

            result["status"] = "success"

        except Exception as e:
            result["status"] = "failed"
            result["error_message"] = str(e)
            logger.error(f"News monitor failed for {source['name']}: {e}")

        self.log_scraper_run(source["url"], result["status"], result["schemes_found"])
        return result

    async def monitor_all_feeds(self) -> dict:
        """Monitor all configured RSS feeds."""
        total_found = 0
        results = []

        for feed in self.RSS_FEEDS:
            try:
                result = await self.scrape(feed)
                results.append(result)
                total_found += result.get("schemes_found", 0)
            except Exception as e:
                logger.error(f"Feed monitor error for {feed['name']}: {e}")

        return {"total_feeds": len(self.RSS_FEEDS), "total_found": total_found, "results": results}

    def _parse_feed(self, xml_content: str) -> list[dict]:
        """Parse RSS/Atom feed XML into list of entries."""
        entries = []
        try:
            root = ET.fromstring(xml_content)

            # Handle RSS 2.0
            for item in root.iter("item"):
                entry = {
                    "title": self._get_text(item, "title"),
                    "link": self._get_text(item, "link"),
                    "description": self._clean_html(self._get_text(item, "description")),
                    "pub_date": self._parse_date(self._get_text(item, "pubDate")),
                }
                if entry["title"]:
                    entries.append(entry)

            # Handle Atom feeds
            if not entries:
                ns = {"atom": "http://www.w3.org/2005/Atom"}
                for item in root.findall(".//atom:entry", ns):
                    title_el = item.find("atom:title", ns)
                    link_el = item.find("atom:link", ns)
                    summary_el = item.find("atom:summary", ns)
                    updated_el = item.find("atom:updated", ns)

                    entry = {
                        "title": title_el.text if title_el is not None else "",
                        "link": link_el.get("href", "") if link_el is not None else "",
                        "description": self._clean_html(summary_el.text or "") if summary_el is not None else "",
                        "pub_date": self._parse_date(updated_el.text or "") if updated_el is not None else None,
                    }
                    if entry["title"]:
                        entries.append(entry)

        except ET.ParseError as e:
            logger.error(f"Failed to parse feed XML: {e}")

        return entries

    def _get_text(self, element, tag: str) -> str:
        """Get text content of a child element."""
        child = element.find(tag)
        return child.text.strip() if child is not None and child.text else ""

    def _clean_html(self, text: str) -> str:
        """Strip HTML tags from text."""
        if not text:
            return ""
        clean = re.sub(r"<[^>]+>", "", text)
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean[:2000]

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Try to parse various date formats from RSS feeds."""
        if not date_str:
            return None

        formats = [
            "%a, %d %b %Y %H:%M:%S %z",      # RSS standard
            "%a, %d %b %Y %H:%M:%S %Z",       # With timezone name
            "%Y-%m-%dT%H:%M:%S%z",             # ISO 8601
            "%Y-%m-%dT%H:%M:%SZ",              # ISO 8601 UTC
            "%Y-%m-%d %H:%M:%S",               # Simple datetime
            "%d %b %Y",                        # Simple date
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                return dt.replace(tzinfo=None)  # Normalize to naive UTC
            except ValueError:
                continue

        return None


# --- Singleton ---
_news_monitor: NewsMonitor | None = None


def get_news_monitor() -> NewsMonitor:
    global _news_monitor
    if _news_monitor is None:
        _news_monitor = NewsMonitor()
    return _news_monitor
