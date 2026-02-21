"""
Jan-Seva AI — Base Scraper
Abstract base class for all scrapers with shared utilities:
  - Rate-limited HTTP fetching with retry
  - Text chunking with overlap
  - Embedding generation & storage
  - Scheme upsert with deduplication
  - Scraper log tracking
"""

import re
import time
import hashlib
import asyncio
import requests
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional
from bs4 import BeautifulSoup

from app.core.supabase_client import get_supabase_client
from app.core.embedding_client import get_embedding_client
from app.utils.logger import logger


class BaseScraper(ABC):
    """
    Abstract base class for all Jan-Seva scrapers.
    Provides: fetch, chunk, embed, store, dedup, rate-limit, retry, logging.
    """

    # Keywords that indicate scheme-related content
    SCHEME_KEYWORDS = [
        "scheme", "yojana", "grant", "subsidy", "aid", "assistance",
        "pension", "scholarship", "benefit", "welfare", "allowance",
        "insurance", "loan", "housing", "skill", "training", "stipend",
        "relief", "compensation", "samman", "nidhi", "abhiyan", "mission",
    ]

    USER_AGENT = "Mozilla/5.0 (compatible; JanSevaBot/1.0; +https://janseva.ai)"

    def __init__(self):
        self._client = get_supabase_client()
        self._embedder = get_embedding_client()
        self._last_request_time = 0.0
        self._min_delay = 2.0  # seconds between requests

    # ══════════════════════════════════════════
    # HTTP Fetch with Rate Limiting & Retry
    # ══════════════════════════════════════════

    def fetch_page(self, url: str, timeout: int = 30, retries: int = 3) -> requests.Response:
        """
        Fetch a URL with rate limiting and exponential backoff retry.
        Respects 2-second minimum between requests.
        """
        for attempt in range(retries):
            # Rate limiting
            elapsed = time.time() - self._last_request_time
            if elapsed < self._min_delay:
                time.sleep(self._min_delay - elapsed)

            try:
                response = requests.get(
                    url,
                    timeout=timeout,
                    headers={"User-Agent": self.USER_AGENT},
                    verify=False,  # Some govt sites have expired certs
                )
                self._last_request_time = time.time()
                response.raise_for_status()
                return response

            except requests.RequestException as e:
                wait = (2 ** attempt) * 2  # 2s, 4s, 8s
                logger.warning(
                    f"Fetch attempt {attempt+1}/{retries} failed for {url}: {e}. "
                    f"Retrying in {wait}s..."
                )
                if attempt < retries - 1:
                    time.sleep(wait)
                else:
                    raise

    def fetch_html(self, url: str) -> BeautifulSoup:
        """Fetch a URL and return parsed BeautifulSoup."""
        response = self.fetch_page(url)
        return BeautifulSoup(response.text, "html.parser")

    # ══════════════════════════════════════════
    # Text Chunking (with overlap)
    # ══════════════════════════════════════════

    def chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
        """
        Split text into chunks with overlap for better RAG retrieval.
        Uses paragraph boundaries when possible.
        """
        if not text or not text.strip():
            return []

        # Clean text
        text = re.sub(r"\s+", " ", text).strip()

        # Split by paragraphs first
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

        chunks = []
        current = ""

        for para in paragraphs:
            if len(current) + len(para) + 1 <= chunk_size:
                current = f"{current} {para}".strip()
            else:
                if current:
                    chunks.append(current)
                # Start new chunk with overlap from previous
                if chunks and overlap > 0:
                    prev_end = chunks[-1][-overlap:]
                    current = f"{prev_end} {para}".strip()
                else:
                    current = para

                # Handle paragraphs longer than chunk_size
                while len(current) > chunk_size:
                    chunks.append(current[:chunk_size])
                    current = current[chunk_size - overlap:]

        if current:
            chunks.append(current)

        return chunks

    # ══════════════════════════════════════════
    # Embedding & Vector Storage
    # ══════════════════════════════════════════

    def create_and_store_embeddings(
        self,
        chunks: list[str],
        scheme_id: Optional[str] = None,
        source_url: str = "",
        source_name: str = "",
    ) -> int:
        """
        Generate embeddings for text chunks and store in Supabase.
        Returns count of embeddings stored.
        """
        if not chunks:
            return 0

        embeddings = self._embedder.embed_batch(chunks)
        stored = 0

        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            try:
                record = {
                    "chunk_text": chunk,
                    "chunk_index": i,
                    "embedding": embedding,
                    "metadata": {
                        "source_url": source_url,
                        "source_name": source_name,
                        "scraped_at": datetime.utcnow().isoformat(),
                    },
                }
                if scheme_id:
                    record["scheme_id"] = scheme_id

                self._client.table("scheme_embeddings").insert(record).execute()
                stored += 1
            except Exception as e:
                logger.error(f"Failed to store embedding chunk {i}: {e}")

        return stored

    # ══════════════════════════════════════════
    # Scheme Upsert with Deduplication
    # ══════════════════════════════════════════

    def generate_slug(self, name: str) -> str:
        """Generate a URL-safe slug from scheme name."""
        slug = name.lower().strip()
        slug = re.sub(r"[^a-z0-9\s-]", "", slug)
        slug = re.sub(r"[\s]+", "-", slug)
        slug = re.sub(r"-+", "-", slug).strip("-")
        return slug[:100]

    def upsert_scheme(self, scheme_data: dict) -> Optional[str]:
        """
        Insert or update a scheme. Deduplicates by slug.
        Returns scheme ID if successful, None if failed.
        """
        name = scheme_data.get("name", "")
        if not name:
            return None

        slug = scheme_data.get("slug") or self.generate_slug(name)
        scheme_data["slug"] = slug

        try:
            # Check if scheme exists by slug
            existing = (
                self._client.table("schemes")
                .select("id")
                .eq("slug", slug)
                .execute()
            )

            if existing.data:
                # Update existing
                scheme_id = existing.data[0]["id"]
                self._client.table("schemes").update(scheme_data).eq("id", scheme_id).execute()
                logger.info(f"Updated scheme: {name}")
                return scheme_id
            else:
                # Insert new
                result = self._client.table("schemes").insert(scheme_data).execute()
                scheme_id = result.data[0]["id"] if result.data else None
                logger.info(f"Inserted new scheme: {name}")
                return scheme_id

        except Exception as e:
            logger.error(f"Failed to upsert scheme '{name}': {e}")
            return None

    # ══════════════════════════════════════════
    # Keyword Detection
    # ══════════════════════════════════════════

    def contains_scheme_keywords(self, text: str) -> bool:
        """Check if text contains scheme-related keywords."""
        text_lower = text.lower()
        return any(kw in text_lower for kw in self.SCHEME_KEYWORDS)

    # ══════════════════════════════════════════
    # Scraper Run Logging
    # ══════════════════════════════════════════

    def log_scraper_run(
        self,
        source_url: str,
        status: str,
        schemes_found: int = 0,
        schemes_updated: int = 0,
        error_message: str = "",
    ):
        """Log a scraper run to the scraper_logs table."""
        try:
            self._client.table("scraper_logs").insert({
                "source_url": source_url,
                "status": status,
                "schemes_found": schemes_found,
                "schemes_updated": schemes_updated,
                "error_message": error_message or None,
            }).execute()
        except Exception as e:
            logger.error(f"Failed to log scraper run: {e}")

    # ══════════════════════════════════════════
    # Abstract Method
    # ══════════════════════════════════════════

    @abstractmethod
    async def scrape(self, source: dict) -> dict:
        """
        Scrape a single source. Must be implemented by subclasses.
        Args:
            source: dict with 'name', 'url', 'type', 'priority' keys
        Returns:
            dict with 'schemes_found', 'status', etc.
        """
        pass
