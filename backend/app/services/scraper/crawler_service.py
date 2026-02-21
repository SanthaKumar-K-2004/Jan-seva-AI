"""
Jan-Seva AI — Crawler Service
Autonomous agent to navigate government portals and discover new schemes.
Uses Playwright for JavaScript-heavy sites.
"""
import asyncio
from typing import List, Dict, Set
from playwright.async_api import async_playwright, Page, BrowserContext
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from app.services.scraper.sector_config import get_sector_config

class CrawlerService:
    def __init__(self):
        self.visited_urls: Set[str] = set()
        self.discovered_schemes: List[Dict] = []

    async def crawl_sector(self, sector: str, max_depth: int = 2) -> List[Dict]:
        """
        Crawls a specific sector's seed URLs to find scheme links.
        """
        config = get_sector_config(sector)
        seeds = config.get("seeds", [])
        
        if not seeds:
            logger.warning(f"No seeds found for sector: {sector}")
            return []

        keywords = config.get("keywords", [])
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
            
            tasks = [self._process_url(context, url, 0, max_depth, keywords) for url in seeds]
            results = await asyncio.gather(*tasks)
            
            await browser.close()
            
            # Flatten results
            all_schemes = []
            for res in results:
                if res:
                    all_schemes.extend(res)
            
            logger.info(f"✅ Crawl complete. Discovered {len(all_schemes)} potential schemes.")
            return all_schemes

    async def _process_url(self, context: BrowserContext, url: str, depth: int, max_depth: int, sector_keywords: List[str]) -> List[Dict]:
        """
        Recursive function to process a single URL.
        """
        if depth > max_depth or url in self.visited_urls:
            return []
        
        self.visited_urls.add(url)
        discovered = []

        try:
            page = await context.new_page()
            try:
                # Go to page with timeout
                await page.goto(url, timeout=30000, wait_until="domcontentloaded")
                
                # Scroll to trigger lazy loading
                await self._auto_scroll(page)
                
                # Extract content
                content = await page.content()
                soup = BeautifulSoup(content, "lxml")
                
                # 1. Identify if THIS page is a scheme detail page
                if self._is_scheme_page(soup, url, sector_keywords):
                    scheme_data = self._extract_basic_info(soup, url)
                    if scheme_data:
                        discovered.append(scheme_data)
                        logger.info(f"Found Scheme: {scheme_data['name']}")

                # 2. Extract links for next depth
                if depth < max_depth:
                    links = self._extract_links(soup, url)
                    # Filter relevant links (same domain or gov.in)
                    relevant_links = [l for l in links if "gov.in" in l or "nic.in" in l]
                    
                    # Sort links by relevance to sector keywords
                    relevant_links.sort(key=lambda l: any(k in l.lower() for k in sector_keywords), reverse=True)
                    
                    # Limit fan-out to prevent explosion
                    relevant_links = relevant_links[:8] 
                    
                    for link in relevant_links:
                        # Sequential processing to be polite
                        sub_results = await self._process_url(context, link, depth + 1, max_depth, sector_keywords)
                        discovered.extend(sub_results)
                        
            except Exception as e:
                logger.warning(f"Error processing {url}: {e}")
            finally:
                await page.close()

        except Exception as e:
            logger.error(f"Failed to open page {url}: {e}")

        return discovered

    async def _auto_scroll(self, page: Page):
        """Scrolls down the page to trigger lazy loading."""
        try:
            for _ in range(3):
                await page.evaluate("window.scrollBy(0, 1000)")
                await asyncio.sleep(1)
        except:
            pass

    def _is_scheme_page(self, soup: BeautifulSoup, url: str, keywords: List[str]) -> bool:
        """
        Heuristic to check if a page describes a specific scheme.
        """
        text = soup.get_text().lower()
        base_keywords = ["eligibility", "benefit", "how to apply", "required documents", "objective"]
        
        score = sum(1 for k in base_keywords if k in text)
        
        # Boost score if sector-specific keywords are present
        score += sum(1 for k in keywords if k in text)
        
        # URL keyword check
        url_lower = url.lower()
        if "scheme" in url_lower or "yojana" in url_lower:
            score += 2
            
        return score >= 4  # Rigorous threshold to avoid junk

    def _extract_basic_info(self, soup: BeautifulSoup, url: str) -> Dict:
        """
        Extracts title and basic metadata from a scheme page.
        """
        title = soup.title.string.strip() if soup.title else "Unknown Scheme"
        
        # Cleanup title
        title = title.replace(" | Government of India", "").replace(" - Portal", "").strip()
        
        return {
            "name": title,
            "source_url": url,
            "raw_html_snippet": str(soup.body)[:5000] if soup.body else "" # Store snippet for later Analysis
        }

    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extracts valid absolute URLs."""
        links = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            full_url = urljoin(base_url, href)
            # Basic validation
            if full_url.startswith("http"):
                links.add(full_url)
        return list(links)

# Singleton
_crawler = None

def get_crawler_service():
    global _crawler
    if _crawler is None:
        _crawler = CrawlerService()
    return _crawler
