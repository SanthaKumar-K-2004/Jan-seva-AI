"""
NVIDIA Qwen 3.5 Client
Used for high-level scheme research and structured data extraction.
"""
import time
import requests
import json
import asyncio
from app.config import get_settings
from app.utils.logger import logger

class NvidiaClient:
    MAX_RETRIES = 3
    BASE_BACKOFF = 10  # seconds

    def __init__(self):
        self.settings = get_settings()
        self.api_key = self.settings.nvidia_api_key
        self.model = self.settings.nvidia_model
        self.invoke_url = "https://integrate.api.nvidia.com/v1/chat/completions"

    async def generate(self, system: str, user_query: str, temperature: float = 0.6) -> str:
        """
        Calls NVIDIA Qwen 3.5 API asynchronously (via thread executor).
        Returns the raw text content. Retries on 429 rate limit errors.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, 
            self._generate_sync, 
            system, 
            user_query, 
            temperature
        )

    def _generate_sync(self, system: str, user_query: str, temperature: float) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_query}
            ],
            "max_tokens": 4096,
            "temperature": temperature,
            "top_p": 0.95,
            "stream": False
        }

        for attempt in range(self.MAX_RETRIES):
            try:
                logger.info(f"🧠 Invoking NVIDIA Qwen 3.5 for: '{user_query[:50]}...'")
                response = requests.post(self.invoke_url, headers=headers, json=payload, timeout=90)
                
                # Handle rate limiting with retry
                if response.status_code == 429:
                    wait = self.BASE_BACKOFF * (2 ** attempt)
                    logger.warning(f"⏳ Rate limited (429). Waiting {wait}s before retry {attempt+1}/{self.MAX_RETRIES}...")
                    time.sleep(wait)
                    continue
                
                response.raise_for_status()
                
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                return content

            except requests.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code == 429:
                    wait = self.BASE_BACKOFF * (2 ** attempt)
                    logger.warning(f"⏳ Rate limited (429). Waiting {wait}s before retry {attempt+1}/{self.MAX_RETRIES}...")
                    time.sleep(wait)
                    continue
                logger.error(f"❌ NVIDIA Qwen API Error: {e}")
                if hasattr(e, 'response') and e.response:
                    logger.error(f"API Response: {e.response.text}")
                raise e
            except Exception as e:
                logger.error(f"❌ NVIDIA Qwen API Error: {e}")
                raise e
        
        raise Exception(f"NVIDIA API failed after {self.MAX_RETRIES} retries (rate limited)")

# Singleton
_nvidia_client = None

def get_nvidia_client():
    global _nvidia_client
    if _nvidia_client is None:
        _nvidia_client = NvidiaClient()
    return _nvidia_client
