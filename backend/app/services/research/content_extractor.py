import httpx
from bs4 import BeautifulSoup
from app.utils.logger import logger

class ContentExtractor:
    """
    Extracts clean text from specific URLs.
    Used when we need deep details from a specific scheme portal.
    """
    
    async def extract(self, url: str) -> str:
        """
        Fetch URL and return cleaned text content.
        """
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        async with httpx.AsyncClient(follow_redirects=True) as client:
            try:
                response = await client.get(url, headers=headers, timeout=15.0)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, "html.parser")
                
                # Remove unwanted elements
                for element in soup(["script", "style", "nav", "footer", "header", "aside", "iframe"]):
                    element.extract()
                
                # Get text
                text = soup.get_text(separator="\n", strip=True)
                
                # Collapse multiple newlines
                clean_text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
                
                return clean_text[:15000] # Limit to 15k chars to fit context
                
            except Exception as e:
                logger.error(f"❌ Extraction failed for {url}: {e}")
                return ""
