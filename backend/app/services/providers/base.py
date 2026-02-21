"""
Jan-Seva AI — Base Provider Interface
All API providers implement this interface for consistent aggregation.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class SearchResult:
    """Single result from any API provider."""
    title: str
    url: str
    content: str
    score: float = 0.0
    source_name: str = ""          # e.g., "Tavily", "DuckDuckGo", "Wikipedia"
    published_date: Optional[str] = None
    domain: str = ""               # e.g., "myscheme.gov.in"
    images: list[str] = field(default_factory=list)


@dataclass
class ProviderResponse:
    """Response from an API provider."""
    results: list[SearchResult] = field(default_factory=list)
    images: list[str] = field(default_factory=list)
    answer: Optional[str] = None   # Direct answer if provider supports it (e.g., Tavily)
    provider_name: str = ""
    success: bool = True
    error: Optional[str] = None
    latency_ms: float = 0.0


class BaseProvider(ABC):
    """Base class for all API providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for logging and attribution."""
        ...

    @abstractmethod
    async def search(self, query: str, max_results: int = 5) -> ProviderResponse:
        """Execute a search and return results."""
        ...

    def is_available(self) -> bool:
        """Check if this provider has valid credentials."""
        return True
