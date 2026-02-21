from typing import List, Optional
import httpx
from app.config import get_settings
from app.utils.logger import logger
from app.services.research.search_service import SearchService, ResearchResponse, SearchResult

class TavilySearchProvider(SearchService):
    """
    Tavily API Provider for AI-optimized search.
    Specializes in getting clean content and relevant images.
    """
    BASE_URL = "https://api.tavily.com/search"

    def __init__(self):
        self.api_key = get_settings().tavily_api_key
        if not self.api_key:
            logger.warning("⚠️ Tavily API Key missing! Set TAVILY_API_KEY in .env")

    async def search(self, query: str, max_results: int = 5) -> ResearchResponse:
        """
        Search using Tavily API.
        """
        if not self.api_key:
            logger.error("❌ Cannot search: Tavily API key is missing")
            return ResearchResponse(results=[], images=[])

        payload = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": "advanced",
            "include_images": True,
            "include_answer": True,
            "max_results": max_results,
            # 'include_domains': [...] # Could restrict to .gov.in if needed, but 'advanced' is smart
        }

        async with httpx.AsyncClient() as client:
            try:
                # 30s timeout as deep search can take time
                response = await client.post(self.BASE_URL, json=payload, timeout=30.0)
                response.raise_for_status()
                data = response.json()
                
                # Parse Results
                search_results = []
                for item in data.get("results", []):
                    search_results.append(SearchResult(
                        title=item.get("title", "Untitled"),
                        url=item.get("url", ""),
                        content=item.get("content", ""),
                        score=item.get("score", 0.0)
                    ))
                
                # Parse Images
                # Tavily returns list of image URLs (strings) or list of dicts depending on version/flags
                # Usually: "images": ["url1", "url2"]
                images = data.get("images", [])
                if images and isinstance(images[0], dict):
                    # Handle if it returns dicts (url, description)
                    images = [img.get("url") for img in images if img.get("url")]

                return ResearchResponse(
                    results=search_results,
                    images=images[:5], # Limit to top 5 images
                    answer=data.get("answer")
                )

            except httpx.HTTPStatusError as e:
                logger.error(f"❌ Tavily API Error {e.response.status_code}: {e.response.text}")
                return ResearchResponse(results=[], images=[])
            except Exception as e:
                logger.error(f"❌ Tavily Unknown Exception: {e}")
                return ResearchResponse(results=[], images=[])
