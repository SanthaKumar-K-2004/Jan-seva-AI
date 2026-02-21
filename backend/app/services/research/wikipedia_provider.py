import httpx
from typing import List
from app.utils.logger import logger
from app.services.research.search_service import SearchService, ResearchResponse, SearchResult

class WikipediaSearchProvider(SearchService):
    """
    Searches Wikipedia for authoritative background information.
    """
    API_URL = "https://en.wikipedia.org/w/api.php"

    async def search(self, query: str, max_results: int = 3) -> ResearchResponse:
        """
        Search Wikipedia Opensearch API.
        """
        params = {
            "action": "opensearch",
            "search": query,
            "limit": max_results,
            "namespace": 0,
            "format": "json"
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(self.API_URL, params=params, timeout=10.0)
                data = response.json()
                # Opensearch returns [query, [titles], [descriptions], [urls]]
                
                if not data or len(data) < 4:
                    return ResearchResponse(results=[])
                
                titles = data[1]
                descriptions = data[2]
                urls = data[3]
                
                results = []
                for i in range(len(titles)):
                    results.append(SearchResult(
                        title=titles[i],
                        url=urls[i],
                        content=descriptions[i],
                        score=1.0 - (i * 0.1) # Arbitrary score based on rank
                    ))
                    
                return ResearchResponse(results=results)

            except Exception as e:
                logger.error(f"❌ Wikipedia search failed: {e}")
                return ResearchResponse(results=[])
