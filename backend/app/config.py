"""
Jan-Seva AI — Application Configuration
API-Only Architecture: All data comes from live API calls.
Zero database dependencies. All config from .env file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App ---
    app_env: str = "development"
    app_debug: bool = True
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # --- AI/LLM (Dual Keys for Fallback) ---
    groq_api_key: str = ""
    groq_api_key_2: str = ""         # Secondary Groq key for failover
    groq_api_key_3: str = ""         # Optional tertiary key
    google_api_key: str = ""
    google_api_key_2: str = ""       # Secondary Gemini key
    google_api_key_3: str = ""       # Optional tertiary key
    openai_api_key: str = ""
    openai_api_key_2: str = ""
    openai_api_key_3: str = ""
    openai_api_keys_csv: str = ""    # Optional comma-separated OpenAI keys
    openai_model: str = "gpt-5-nano"
    openai_max_tokens: int = 4096
    llm_max_tokens: int = 4096
    llm_temperature: float = 0.15
    enable_openai_research_provider: bool = True

    # --- NVIDIA (Qwen 3.5 Deep Research) ---
    nvidia_api_key: str = ""
    nvidia_api_key_glm: str = ""
    nvidia_model: str = "qwen/qwen3.5-397b-a17b"

    # --- Search APIs ---
    tavily_api_key: str = ""         # AI-optimized search

    # --- News API ---
    news_api_key: str = ""
    news_allowed_domains_csv: str = (
        "pib.gov.in,thehindu.com,economictimes.indiatimes.com,"
        "business-standard.com,livemint.com,hindustantimes.com"
    )

    # --- Source Quality / Verification ---
    strict_verified_mode: bool = True
    min_source_reliability: float = 0.67
    max_source_age_days: int = 45
    max_news_age_days: int = 21
    require_multi_source_for_news: bool = True

    # --- Research Cache ---
    research_cache_enabled: bool = True
    research_cache_ttl_minutes: int = 180
    research_cache_path: str = "data/research_cache.sqlite3"

    # --- Wikipedia API ---
    wikipedia_client_id: str = ""
    wikipedia_client_secret: str = ""
    wikipedia_access_token: str = ""

    # --- Voice ---
    whisper_model_size: str = "base"

    # --- Translation (Bhashini) ---
    bhashini_user_id: str = ""
    bhashini_api_key: str = ""

    # --- WhatsApp ---
    whatsapp_verify_token: str = ""
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""

    # --- Supabase (optional, used by analytics/admin) ---
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""

    # --- Derived ---
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def all_groq_keys(self) -> list[str]:
        """Returns all available Groq API keys for rotation."""
        return [k for k in [self.groq_api_key, self.groq_api_key_2, self.groq_api_key_3] if k]

    @property
    def all_google_keys(self) -> list[str]:
        """Returns all available Google API keys for rotation."""
        return [k for k in [self.google_api_key, self.google_api_key_2, self.google_api_key_3] if k]

    @property
    def all_openai_keys(self) -> list[str]:
        """Returns all available OpenAI API keys (deduplicated)."""
        raw_keys = [self.openai_api_key, self.openai_api_key_2, self.openai_api_key_3]
        if self.openai_api_keys_csv:
            raw_keys.extend(k.strip() for k in self.openai_api_keys_csv.split(","))

        seen = set()
        ordered = []
        for key in raw_keys:
            if not key:
                continue
            if key in seen:
                continue
            seen.add(key)
            ordered.append(key)
        return ordered

    @property
    def news_allowed_domains(self) -> list[str]:
        return [d.strip().lower() for d in self.news_allowed_domains_csv.split(",") if d.strip()]

@lru_cache()
def get_settings() -> Settings:
    """Cached singleton for application settings."""
    return Settings()
