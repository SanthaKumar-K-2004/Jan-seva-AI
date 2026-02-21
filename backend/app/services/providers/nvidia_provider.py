"""
Jan-Seva AI — NVIDIA Deep Research Provider
Uses NVIDIA Qwen 3.5 for deep scheme analysis and structured data extraction.
"""

import time
import asyncio
import requests
from app.config import get_settings
from app.utils.logger import logger
from app.services.providers.base import BaseProvider, ProviderResponse, SearchResult


NVIDIA_SYSTEM_PROMPT = """You are an expert on Indian government schemes, policies, and welfare programs.
When given a query about a government scheme:
1. Provide the OFFICIAL scheme name
2. List exact eligibility criteria (age, income, caste, state)
3. Quote exact benefit amounts (₹)
4. Mention documents required
5. Provide official portal URL if known
6. Note the current status (active/expired/modified)

Be factual. If you're unsure about specific details, say so.
Format your response with clear sections."""


class NvidiaProvider(BaseProvider):
    """NVIDIA Qwen 3.5 — for deep, AI-powered scheme research and analysis."""

    INVOKE_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
    MAX_RETRIES = 2
    BASE_BACKOFF = 5

    def __init__(self):
        settings = get_settings()
        self.api_keys = [k for k in [settings.nvidia_api_key, settings.nvidia_api_key_glm] if k]
        self.model = settings.nvidia_model
        self._current_key_idx = 0

    @property
    def name(self) -> str:
        return "NVIDIA-Qwen"

    def is_available(self) -> bool:
        return len(self.api_keys) > 0

    def _get_api_key(self) -> str:
        """Rotate through available API keys."""
        key = self.api_keys[self._current_key_idx % len(self.api_keys)]
        self._current_key_idx += 1
        return key

    async def search(self, query: str, max_results: int = 1) -> ProviderResponse:
        """Uses NVIDIA Qwen to generate deep scheme analysis."""
        if not self.is_available():
            return ProviderResponse(provider_name=self.name, success=False, error="API keys missing")

        start = time.monotonic()
        try:
            loop = asyncio.get_running_loop()
            answer = await loop.run_in_executor(None, self._generate_sync, query)

            latency = (time.monotonic() - start) * 1000
            logger.info(f"🧠 NVIDIA Qwen: response in {latency:.0f}ms")

            return ProviderResponse(
                results=[SearchResult(
                    title=f"AI Research: {query[:80]}",
                    url="https://build.nvidia.com",
                    content=answer,
                    score=0.85,
                    source_name=self.name,
                    domain="nvidia.com",
                )],
                answer=answer,
                provider_name=self.name,
                latency_ms=latency,
            )

        except Exception as e:
            latency = (time.monotonic() - start) * 1000
            logger.error(f"❌ NVIDIA Qwen failed: {e}")
            return ProviderResponse(provider_name=self.name, success=False, error=str(e), latency_ms=latency)

    def _generate_sync(self, query: str) -> str:
        for attempt in range(self.MAX_RETRIES):
            api_key = self._get_api_key()
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": NVIDIA_SYSTEM_PROMPT},
                    {"role": "user", "content": query},
                ],
                "max_tokens": 4096,
                "temperature": 0.4,
                "top_p": 0.95,
                "stream": False,
            }

            try:
                response = requests.post(self.INVOKE_URL, headers=headers, json=payload, timeout=60)

                if response.status_code == 429:
                    wait = self.BASE_BACKOFF * (2 ** attempt)
                    logger.warning(f"⏳ NVIDIA rate limited. Waiting {wait}s (attempt {attempt + 1}/{self.MAX_RETRIES})")
                    import time as t
                    t.sleep(wait)
                    continue

                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"]

            except requests.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code == 429:
                    continue
                raise

        raise Exception(f"NVIDIA API failed after {self.MAX_RETRIES} retries")
