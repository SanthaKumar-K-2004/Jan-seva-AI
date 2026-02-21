"""
Jan-Seva AI — Web Search Service
Uses manual scraping of DuckDuckGo HTML version to fetch real-time information.
This implementation is robust against library deprecations and API failures.
"""

import requests
from bs4 import BeautifulSoup
from app.utils.logger import logger
import asyncio
import functools
import re

class WebSearchService:
    """
    Search service wrapper for DuckDuckGo (HTML Version).
    Scrapes https://html.duckduckgo.com/html/ to bypass API limits.
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
             "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        })

    async def search(self, query: str, limit: int = 5) -> str:
        """
        Performs a web search and returns a markdown-formatted summary of results.
        Returns empty string if search fails.
        """
        try:
            logger.info(f"🔍 Searching Web (DDG HTML) for: '{query}'")

            # Run sync scraping in a thread
            loop = asyncio.get_running_loop()
            results = await loop.run_in_executor(
                None, 
                functools.partial(self._scrape_ddg_html, query, limit)
            )

            if not results:
                logger.warning(f"⚠️ No web results found for: '{query}'")
                return ""

            # Format results for LLM Context
            formatted_parts = [f"🌐 **Web Search Results for '{query}':**"]
            
            for i, res in enumerate(results, 1):
                title = res.get("title", "No Title")
                link = res.get("href", "#")
                snippet = res.get("snippet", "No description available.")
                
                formatted_parts.append(
                    f"{i}. **[{title}]({link})**\n   {snippet}"
                )
            
            return "\n\n".join(formatted_parts)

        except Exception as e:
            logger.error(f"❌ Web search failed: {e}")
            return ""

    def _scrape_ddg_html(self, query: str, limit: int):
        """
        Scrapes HTML from DuckDuckGo lite version.
        This version is lighter and less likely to block simple requests.
        """
        try:
            url = "https://html.duckduckgo.com/html/"
            data = {"q": query}
            
            # Use a timeout to prevent hanging
            res = self.session.post(url, data=data, timeout=5)
            
            if res.status_code != 200:
                logger.warning(f"DDG returned status code: {res.status_code}")
                return []

            soup = BeautifulSoup(res.text, "html.parser")
            results = []
            
            # Iterate over result links
            # Structure: 
            # <div class="result ...">
            #   <h2 class="result__title"><a class="result__a" href="...">Title</a></h2>
            #   <a class="result__snippet" href="...">Snippet...</a>
            # </div>
            
            # We look for result__a
            links = soup.find_all("a", class_="result__a")
            
            for link in links:
                if len(results) >= limit:
                    break
                    
                title = link.text.strip()
                href = link.get("href")
                snippet = ""
                
                # Try to find snippet in the same result container
                # Traverse up to find the result div
                result_div = link.find_parent("div", class_="result__body") or link.find_parent("div", class_="result")
                
                if result_div:
                    snippet_tag = result_div.find("a", class_="result__snippet")
                    if snippet_tag:
                        snippet = snippet_tag.text.strip()

                if href and title:
                    # Clean up DDG redirect URLs if possible, but raw URLs work okay
                    # DDG HTML URLs are often /l/?kh=-1&uddg=...
                    # We can try to extract the real URL but for RAG context it might not matter
                    # as long as the content is in the title/snippet.
                    
                    # Decent cleanup attempt:
                    if "/l/?" in href:
                        # try to extract 'uddg' param
                        match = re.search(r'uddg=([^&]+)', href)
                        if match:
                             from urllib.parse import unquote
                             href = unquote(match.group(1))

                    results.append({
                        "title": title,
                        "href": href,
                        "snippet": snippet
                    })
            
            return results

        except Exception as e:
            logger.error(f"DDG Scraping Error: {e}")
            return []


# --- Singleton ---
_web_search_service: WebSearchService | None = None


def get_web_search_service() -> WebSearchService:
    """Returns a cached Web Search Service instance."""
    global _web_search_service
    if _web_search_service is None:
        _web_search_service = WebSearchService()
    return _web_search_service
