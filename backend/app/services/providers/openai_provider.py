"""
Jan-Seva AI — OpenAI Provider
Wraps OpenAI GPT-5 Nano (or other models) for deep research and reasoning.
"""

import time
import asyncio
from app.core.openai_client import get_openai_client
from app.services.providers.base import BaseProvider, ProviderResponse, SearchResult
from app.utils.logger import logger

class OpenAIProvider(BaseProvider):
    """OpenAI — for high-performance reasoning and scheme research."""

    def __init__(self):
        self.client = get_openai_client()

    @property
    def name(self) -> str:
        return "OpenAI"

    def is_available(self) -> bool:
        return self.client.async_client is not None

    async def search(self, query: str, max_results: int = 1) -> ProviderResponse:
        """
        Uses OpenAI to generate deep scheme analysis. 
        Note: This acts as a 'Reasoning' provider similar to NVIDIA.
        """
        if not self.is_available():
            return ProviderResponse(provider_name=self.name, success=False, error="OpenAI client unavailable")

        start = time.monotonic()
        try:
            # We use a system prompt tailored for research
            system_prompt = (
                "You are an expert Government Scheme Researcher. "
                "Analyze the user's query and provide detailed, structured information."
            )
            
            answer = await self.client.generate(system_prompt, query)

            latency = (time.monotonic() - start) * 1000
            logger.info(f"🧠 OpenAI: response in {latency:.0f}ms")

            return ProviderResponse(
                results=[SearchResult(
                    title=f"AI Research: {query[:80]}",
                    url="https://openai.com",
                    content=answer,
                    score=0.95,
                    source_name=self.name,
                    domain="openai.com",
                )],
                answer=answer,
                provider_name=self.name,
                latency_ms=latency,
            )

        except Exception as e:
            latency = (time.monotonic() - start) * 1000
            logger.error(f"❌ OpenAI failed: {e}")
            return ProviderResponse(provider_name=self.name, success=False, error=str(e), latency_ms=latency)
