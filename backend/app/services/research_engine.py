from typing import List, Dict, Any, Optional
import asyncio
from app.services.research.tavily_provider import TavilySearchProvider
from app.services.research.wikipedia_provider import WikipediaSearchProvider
from app.services.research.content_extractor import ContentExtractor
from app.core.llm_client import get_llm_client
from app.utils.logger import logger

class ResearchEngine:
    """
    Orchestrates the Research -> Synthesis pipeline.
    Connects to multiple authoritative sources and synthesizes the result.
    """
    
    def __init__(self):
        self.tavily = TavilySearchProvider()
        self.wikipedia = WikipediaSearchProvider()
        self.extractor = ContentExtractor()
        self.llm = get_llm_client()

    async def research_scheme(
        self, 
        query: str, 
        user_profile: Optional[Dict] = None, 
        language: str = "en"
    ) -> Dict[str, Any]:
        """
        Conducts deep research on a scheme query and returns a synthesized answer.
        """
        logger.info(f"🕵️ Researching: '{query}' (Lang: {language})")

        # 1. Parallel Search Execution
        # We run Tavily and Wikipedia in parallel for speed
        tavily_task = self.tavily.search(query, max_results=5)
        wiki_task = self.wikipedia.search(query, max_results=3)
        
        results = await asyncio.gather(tavily_task, wiki_task, return_exceptions=True)
        
        tavily_resp = results[0] if not isinstance(results[0], Exception) else None
        wiki_resp = results[1] if not isinstance(results[1], Exception) else None
        
        if not tavily_resp and not wiki_resp:
            return {
                "answer": "I'm sorry, I couldn't connect to my research tools right now. Please check your internet connection.",
                "sources": [],
                "images": []
            }

        # 2. Result Aggregation
        all_results = []
        images = []
        
        if tavily_resp:
            all_results.extend(tavily_resp.results)
            images.extend(tavily_resp.images)
            
        if wiki_resp:
            all_results.extend(wiki_resp.results)
            
        # Deduplicate results by URL
        seen_urls = set()
        unique_results = []
        for res in all_results:
            if res.url not in seen_urls:
                unique_results.append(res)
                seen_urls.add(res.url)
        
        # 3. Context Construction for LLM
        context_parts = ["RESEARCH DATA FROM LIVE SOURCES:\n"]
        
        # Add Tavily's direct answer if available
        if tavily_resp and tavily_resp.answer:
            context_parts.append(f"Quick Knowledge: {tavily_resp.answer}\n")
            
        for i, res in enumerate(unique_results[:8]): # Top 8 results
            context_parts.append(f"--- SOURCE {i+1} ---\nTitle: {res.title}\nURL: {res.url}\nContent: {res.content[:2000]}\n")
            
        if images:
            context_parts.append(f"\nAVAILABLE IMAGES (Embed these if relevant):\n")
            for img in images[:4]:
                context_parts.append(f"- {img}")

        if user_profile:
             context_parts.append(f"\nUSER PROFILE CONTEXT:\n{str(user_profile)}")

        final_context = "\n".join(context_parts)
        
        # 4. LLM Synthesis
        # We pass this rich context to our "Expert Mentor" LLM
        answer = await self.llm.generate(
            user_query=query, 
            context=final_context, 
            language=language,
            is_greeting=False
        )
        
        # 5. Return Structured Response
        return {
            "answer": answer,
            "sources": [res.dict() for res in unique_results[:5]], # Return top sources for UI citations
            "images": images[:4]
        }

# Singleton
_research_engine = None

def get_research_engine() -> ResearchEngine:
    global _research_engine
    if not _research_engine:
        _research_engine = ResearchEngine()
    return _research_engine
