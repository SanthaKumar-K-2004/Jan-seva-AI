"""
Jan-Seva AI - OpenAI Client
Provides multi-key OpenAI access with key rotation/failover.
"""

from openai import OpenAI, AsyncOpenAI
from app.config import get_settings
from app.utils.logger import logger


def _is_token_error(message: str) -> bool:
    text = message.lower()
    return any(
        token_hint in text
        for token_hint in (
            "max_tokens",
            "max_output_tokens",
            "context length",
            "context_length",
            "too many tokens",
            "token limit",
        )
    )


class OpenAIClient:
    """
    OpenAI wrapper with:
    - multiple API key rotation/failover
    - chat completions
    - responses.create fallback
    """

    def __init__(self):
        self.settings = get_settings()
        self.model = self.settings.openai_model
        self.max_tokens = self.settings.openai_max_tokens
        self.api_keys = self.settings.all_openai_keys
        self._next_key_index = 0

        if not self.api_keys:
            logger.warning("OpenAI API keys are missing. OpenAI services will be unavailable.")
            self.clients = []
            self.async_clients = []
            self.client = None
            self.async_client = None
            return

        self.clients = [OpenAI(api_key=key) for key in self.api_keys]
        self.async_clients = [AsyncOpenAI(api_key=key) for key in self.api_keys]

        # Backward-compatible aliases for old call sites.
        self.client = self.clients[0]
        self.async_client = self.async_clients[0]

        logger.info(
            f"OpenAI Client initialized with model={self.model}, "
            f"keys={len(self.api_keys)}, max_tokens={self.max_tokens}"
        )

    def _key_order(self) -> list[int]:
        if not self.async_clients:
            return []
        total = len(self.async_clients)
        start = self._next_key_index % total
        self._next_key_index = (start + 1) % total
        return [(start + i) % total for i in range(total)]

    def _token_chain(self) -> list[int]:
        raw = [self.max_tokens, 4096, 3072, 2048, 1024]
        chain = []
        for value in raw:
            if value and value > 0 and value not in chain:
                chain.append(value)
        return chain

    async def generate(self, system_prompt: str, user_query: str, temperature: float = 0.4) -> str:
        """Generate completion using chat completions with key/token fallback."""
        if not self.async_clients:
            raise RuntimeError("OpenAI client not initialized (missing API key)")

        last_error = None
        key_order = self._key_order()
        token_chain = self._token_chain()

        for key_index in key_order:
            client = self.async_clients[key_index]
            for max_tokens in token_chain:
                try:
                    logger.info(
                        f"OpenAI generate: key#{key_index + 1}/{len(self.async_clients)} "
                        f"model={self.model} max_tokens={max_tokens}"
                    )
                    response = await client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_query},
                        ],
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    answer = (response.choices[0].message.content or "").strip()
                    if answer:
                        return answer
                except Exception as exc:
                    last_error = exc
                    if _is_token_error(str(exc)):
                        logger.warning(
                            f"OpenAI token-limit issue on key#{key_index + 1}; "
                            f"retrying with lower max_tokens. Error: {exc}"
                        )
                        continue
                    logger.warning(f"OpenAI key#{key_index + 1} failed: {exc}")
                    break

        logger.error(f"OpenAI generate failed on all keys. Last error: {last_error}")
        raise RuntimeError(f"OpenAI generate failed across all keys: {last_error}")

    async def create_response(self, input_text: str, store: bool = True) -> str:
        """
        Use responses.create when available.
        Falls back to generate() on failures.
        """
        if not self.async_clients:
            raise RuntimeError("OpenAI client not initialized")

        last_error = None
        for key_index in self._key_order():
            client = self.async_clients[key_index]
            try:
                logger.info(f"OpenAI responses.create: key#{key_index + 1} model={self.model}")
                response = await client.responses.create(
                    model=self.model,
                    input=input_text,
                    store=store,
                )

                if hasattr(response, "output_text") and response.output_text:
                    return response.output_text
                if hasattr(response, "content") and response.content:
                    return response.content
                return str(response)
            except Exception as exc:
                last_error = exc
                logger.warning(f"OpenAI responses.create failed on key#{key_index + 1}: {exc}")
                continue

        logger.warning(
            f"responses.create failed for all keys; falling back to chat completions. "
            f"Last error: {last_error}"
        )
        return await self.generate("You are a helpful assistant.", input_text)


_openai_client = None


def get_openai_client() -> OpenAIClient:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAIClient()
    return _openai_client
