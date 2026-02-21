"""
Jan-Seva AI — Google Gemini Provider
Uses Google Gemini for fast, intelligent scheme research.
"""

import time
import httpx
from app.config import get_settings
from app.utils.logger import logger
from app.services.providers.base import BaseProvider, ProviderResponse, SearchResult


GEMINI_SYSTEM_PROMPT = """You are an expert researcher on Indian government schemes and welfare programs.
For the given query, provide accurate, structured information about relevant schemes including:
- Exact scheme names
- Eligibility criteria
- Benefits and amounts
- How to apply
- Official websites
Be concise and factual. Focus on the most relevant schemes."""


class GoogleGeminiProvider(BaseProvider):
    """Google Gemini — fast AI research with dual key rotation."""

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

    def __init__(self):
        settings = get_settings()
        self.api_keys = settings.all_google_keys
        self._current_key_idx = 0

    @property
    def name(self) -> str:
        return "Gemini"

    def is_available(self) -> bool:
        return len(self.api_keys) > 0

    def _get_api_key(self) -> str:
        key = self.api_keys[self._current_key_idx % len(self.api_keys)]
        self._current_key_idx += 1
        return key

    async def search(self, query: str, max_results: int = 1) -> ProviderResponse:
        if not self.is_available():
            return ProviderResponse(provider_name=self.name, success=False, error="API keys missing")

        start = time.monotonic()

        for attempt in range(len(self.api_keys)):
            try:
                api_key = self._get_api_key()
                url = f"{self.BASE_URL}?key={api_key}"

                payload = {
                    "contents": [
                        {
                            "parts": [
                                {"text": f"{GEMINI_SYSTEM_PROMPT}\n\nUser Query: {query}"}
                            ]
                        }
                    ],
                    "generationConfig": {
                        "temperature": 0.3,
                        "maxOutputTokens": 2048,
                    }
                }

                async with httpx.AsyncClient() as client:
                    response = await client.post(url, json=payload, timeout=30.0)
                    response.raise_for_status()
                    data = response.json()

                answer = ""
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    answer = " ".join(p.get("text", "") for p in parts)

                latency = (time.monotonic() - start) * 1000
                logger.info(f"💎 Gemini: response in {latency:.0f}ms")

                return ProviderResponse(
                    results=[SearchResult(
                        title=f"Gemini Research: {query[:80]}",
                        url="https://ai.google.dev",
                        content=answer,
                        score=0.8,
                        source_name=self.name,
                        domain="google.com",
                    )],
                    answer=answer,
                    provider_name=self.name,
                    latency_ms=latency,
                )

            except Exception as e:
                logger.warning(f"⚠️ Gemini key {attempt + 1} failed: {e}")
                continue

        latency = (time.monotonic() - start) * 1000
        return ProviderResponse(provider_name=self.name, success=False, error="All Gemini keys failed", latency_ms=latency)
