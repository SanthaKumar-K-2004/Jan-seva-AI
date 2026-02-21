from abc import ABC, abstractmethod
from typing import List, Optional
from pydantic import BaseModel

class SearchResult(BaseModel):
    """A single search result item."""
    title: str = ""
    url: str = ""
    content: str = ""
    score: float = 0.0

class ResearchResponse(BaseModel):
    """Aggregate response from a search provider."""
    results: List[SearchResult]
    images: List[str] = []
    answer: Optional[str] = None  # Direct answer from the provider if available

class SearchService(ABC):
    """Abstract base class for search providers."""
    
    @abstractmethod
    async def search(self, query: str, max_results: int = 5) -> ResearchResponse:
        """
        Execute a search query.
        
        Args:
            query: The search query string
            max_results: Maximum number of text results to return
            
        Returns:
            ResearchResponse containing text results and images
        """
        pass
