"""
Jan-Seva AI — Portal Scraper (Selenium + API + HTML)
Three scraping strategies:
  1. MyScheme.gov.in API — Richest structured source
  2. Selenium Scraper — For JS-heavy sites (MyScheme detail pages, state portals)
  3. HTML Scraper — For simple HTML pages using BeautifulSoup
"""

import re
import json
import time
from typing import Optional
from datetime import datetime

from app.services.scraper.base_scraper import BaseScraper
from app.utils.logger import logger


class MySchemeAPIScraper(BaseScraper):
    """
    Scrapes MyScheme.gov.in using its internal search API.
    Richest structured source with 500+ central/state schemes.
    """

    BASE_URL = "https://www.myscheme.gov.in"
    API_URL = "https://www.myscheme.gov.in/api/v1/schemes"

    async def scrape(self, source: dict) -> dict:
        """Scrape all schemes from MyScheme.gov.in API."""
        result = {"source": source["name"], "schemes_found": 0, "schemes_updated": 0, "status": "started"}

        try:
            page = 1
            per_page = 50
            total_scraped = 0

            while True:
                try:
                    response = self.fetch_page(
                        f"{self.API_URL}?page={page}&per_page={per_page}",
                        timeout=30,
                    )
                    data = response.json()
                except Exception:
                    logger.warning("MyScheme API unavailable, falling back to Selenium")
                    return await self._scrape_selenium_fallback(source)

                schemes = data.get("data", data.get("schemes", []))
                if not schemes:
                    break

                for scheme_raw in schemes:
                    scheme_data = self._parse_myscheme_response(scheme_raw)
                    if scheme_data:
                        scheme_id = self.upsert_scheme(scheme_data)
                        if scheme_id:
                            embed_text = (
                                f"{scheme_data['name']}. "
                                f"{scheme_data.get('description', '')}. "
                                f"Benefits: {scheme_data.get('benefits', '')}."
                            )
                            chunks = self.chunk_text(embed_text)
                            self.create_and_store_embeddings(
                                chunks, scheme_id, source["url"], source["name"]
                            )
                            total_scraped += 1

                page += 1
                if page > 10:
                    break

            result["schemes_found"] = total_scraped
            result["status"] = "success"

        except Exception as e:
            result["status"] = "failed"
            result["error_message"] = str(e)
            logger.error(f"MyScheme scraper failed: {e}")

        self.log_scraper_run(source["url"], result["status"], result["schemes_found"])
        return result

    def _parse_myscheme_response(self, raw: dict) -> Optional[dict]:
        """Parse MyScheme API response into our scheme format."""
        try:
            name = raw.get("schemeName", raw.get("title", raw.get("name", "")))
            if not name:
                return None

            return {
                "name": name,
                "slug": self.generate_slug(name),
                "description": raw.get("schemeDescription", raw.get("description", "")),
                "ministry": raw.get("ministry", raw.get("nodalMinistry", "")),
                "department": raw.get("department", raw.get("nodalDepartment", "")),
                "state": raw.get("state", "Central"),
                "category": raw.get("categories", raw.get("tags", [])),
                "benefits": raw.get("benefits", raw.get("schemeBenefits", "")),
                "documents_required": raw.get("documentsRequired", []),
                "how_to_apply": raw.get("howToApply", raw.get("applicationProcess", "")),
                "application_url": raw.get("applicationUrl", raw.get("schemeUrl", "")),
                "source_url": f"{self.BASE_URL}/schemes/{self.generate_slug(name)}",
                "source_type": "api",
            }
        except Exception as e:
            logger.warning(f"Failed to parse MyScheme entry: {e}")
            return None

    async def _scrape_selenium_fallback(self, source: dict) -> dict:
        """Fallback: use Selenium for MyScheme.gov.in if API is blocked."""
        selenium_scraper = SeleniumPortalScraper()
        return await selenium_scraper.scrape(source)


class SeleniumPortalScraper(BaseScraper):
    """
    Selenium-powered scraper for JavaScript-heavy government portals.
    Uses undetected-chromedriver to avoid bot detection.
    """

    async def scrape(self, source: dict) -> dict:
        """Scrape a JS-heavy portal page using Selenium."""
        result = {"source": source["name"], "schemes_found": 0, "status": "started"}

        driver = None
        try:
            driver = self._get_driver()
            if not driver:
                # Fallback to plain HTML if Selenium fails
                logger.warning("Selenium not available, falling back to HTML scraping")
                html_scraper = HTMLPortalScraper()
                return await html_scraper.scrape(source)

            # Navigate to page
            driver.get(source["url"])
            time.sleep(3)  # Wait for JS to render

            # Scroll down to load dynamic content
            for _ in range(3):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)

            # Get rendered page source
            page_source = driver.page_source

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(page_source, "html.parser")

            # Find scheme links/cards
            scheme_elements = []

            # Common patterns for scheme listings
            for selector in [
                "a[href*='scheme']", ".scheme-card", ".scheme-item",
                ".card", ".list-group-item", "div[class*='scheme']",
                "table tr", "li a",
            ]:
                elements = soup.select(selector)
                if elements:
                    scheme_elements.extend(elements)

            # Process found elements
            seen_slugs = set()
            for el in scheme_elements[:50]:
                scheme = self._extract_scheme_from_element(el, source)
                if scheme and scheme["slug"] not in seen_slugs:
                    seen_slugs.add(scheme["slug"])
                    scheme_id = self.upsert_scheme(scheme)
                    if scheme_id:
                        embed_text = f"{scheme['name']}. {scheme.get('description', '')}"
                        chunks = self.chunk_text(embed_text)
                        self.create_and_store_embeddings(
                            chunks, scheme_id, source["url"], source["name"]
                        )
                        result["schemes_found"] += 1

            # Also scrape individual scheme pages if possible
            scheme_links = []
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if "/schemes/" in href or "/scheme/" in href:
                    full_url = href if href.startswith("http") else f"{source['url'].rstrip('/')}{href}"
                    if full_url not in scheme_links:
                        scheme_links.append(full_url)

            for url in scheme_links[:20]:
                try:
                    detail = self._scrape_scheme_detail_selenium(driver, url, source)
                    if detail and detail["slug"] not in seen_slugs:
                        seen_slugs.add(detail["slug"])
                        scheme_id = self.upsert_scheme(detail)
                        if scheme_id:
                            embed_text = f"{detail['name']}. {detail.get('description', '')}"
                            chunks = self.chunk_text(embed_text)
                            self.create_and_store_embeddings(
                                chunks, scheme_id, url, source["name"]
                            )
                            result["schemes_found"] += 1
                except Exception as e:
                    logger.warning(f"Failed to scrape detail page {url}: {e}")

            result["status"] = "success"

        except Exception as e:
            result["status"] = "failed"
            result["error_message"] = str(e)
            logger.error(f"Selenium scraper failed for {source['name']}: {e}")

        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass

        self.log_scraper_run(source["url"], result["status"], result["schemes_found"])
        return result

    def _get_driver(self):
        """Create Selenium Chrome driver with stealth options."""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options

            options = Options()
            options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
            options.add_argument(f"--user-agent={self.USER_AGENT}")

            # Try undetected-chromedriver first
            try:
                import undetected_chromedriver as uc
                driver = uc.Chrome(options=options, headless=True)
                return driver
            except Exception:
                pass

            # Fallback to regular webdriver
            driver = webdriver.Chrome(options=options)
            return driver

        except Exception as e:
            logger.error(f"Failed to create Selenium driver: {e}")
            return None

    def _scrape_scheme_detail_selenium(self, driver, url: str, source: dict) -> Optional[dict]:
        """Scrape a single scheme detail page using Selenium."""
        try:
            driver.get(url)
            time.sleep(2)

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(driver.page_source, "html.parser")

            title = soup.find("h1") or soup.find("h2")
            name = title.get_text(strip=True) if title else ""
            if not name or len(name) < 5:
                return None

            # Extract description
            content = soup.find("div", class_=re.compile(r"content|description|detail|main", re.I))
            description = content.get_text(strip=True)[:2000] if content else ""

            return {
                "name": name,
                "slug": self.generate_slug(name),
                "description": description,
                "source_url": url,
                "source_type": "selenium",
                "state": self._detect_state_from_source(source),
            }
        except Exception:
            return None

    def _extract_scheme_from_element(self, element, source: dict) -> Optional[dict]:
        """Extract scheme info from an HTML element."""
        try:
            name = ""
            link = element if element.name == "a" else element.find("a")
            heading = element.find(["h1", "h2", "h3", "h4", "h5"])

            if heading:
                name = heading.get_text(strip=True)
            elif link:
                name = link.get_text(strip=True)
            else:
                name = element.get_text(strip=True)[:100]

            if not name or len(name) < 5:
                return None

            desc_el = element.find("p") or element.find("div", class_=re.compile(r"desc|detail|content", re.I))
            description = desc_el.get_text(strip=True)[:1000] if desc_el else ""

            url = ""
            if link and link.get("href"):
                href = link["href"]
                url = href if href.startswith("http") else f"{source['url'].rstrip('/')}/{href.lstrip('/')}"

            return {
                "name": name,
                "slug": self.generate_slug(name),
                "description": description,
                "state": self._detect_state_from_source(source),
                "source_url": url or source["url"],
                "source_type": "selenium",
                "ministry": source.get("name", ""),
            }
        except Exception:
            return None

    def _detect_state_from_source(self, source: dict) -> str:
        """Detect state from source name."""
        name = source.get("name", "").lower()
        state_map = {
            "tamil": "Tamil Nadu", "tn ": "Tamil Nadu",
            "kerala": "Kerala",
            "andhra": "Andhra Pradesh", "ap ": "Andhra Pradesh",
            "karnataka": "Karnataka",
            "maharashtra": "Maharashtra", "mh ": "Maharashtra",
            "uttar": "Uttar Pradesh", "up ": "Uttar Pradesh",
            "rajasthan": "Rajasthan",
        }
        for key, state in state_map.items():
            if key in name:
                return state
        return "Central"


class HTMLPortalScraper(BaseScraper):
    """
    Generic HTML scraper for government portal pages.
    Works for simpler sites using BeautifulSoup.
    """

    async def scrape(self, source: dict) -> dict:
        """Scrape scheme data from an HTML portal page."""
        result = {"source": source["name"], "schemes_found": 0, "status": "started"}

        try:
            soup = self.fetch_html(source["url"])

            schemes_found = []
            selectors = [
                "a[href*='scheme']",
                ".scheme-card", ".scheme-item", ".scheme-list li",
                "table tr", ".card", ".list-group-item",
                "div[class*='scheme']", "div[class*='Scheme']",
            ]

            for selector in selectors:
                elements = soup.select(selector)
                if elements:
                    for el in elements[:30]:
                        scheme = self._extract_scheme(el, source)
                        if scheme and scheme["name"]:
                            schemes_found.append(scheme)
                    if schemes_found:
                        break

            # Fallback: treat entire page as content
            if not schemes_found:
                page_text = soup.get_text(separator="\n", strip=True)
                if self.contains_scheme_keywords(page_text):
                    chunks = self.chunk_text(page_text)
                    self.create_and_store_embeddings(
                        chunks, None, source["url"], source["name"]
                    )
                    result["schemes_found"] = 1
                    result["status"] = "success"
                    self.log_scraper_run(source["url"], "success", 1)
                    return result

            seen_slugs = set()
            for scheme_data in schemes_found:
                slug = scheme_data.get("slug", "")
                if slug in seen_slugs:
                    continue
                seen_slugs.add(slug)

                scheme_id = self.upsert_scheme(scheme_data)
                if scheme_id:
                    embed_text = f"{scheme_data['name']}. {scheme_data.get('description', '')}"
                    chunks = self.chunk_text(embed_text)
                    self.create_and_store_embeddings(
                        chunks, scheme_id, source["url"], source["name"]
                    )
                    result["schemes_found"] += 1

            result["status"] = "success"

        except Exception as e:
            result["status"] = "failed"
            result["error_message"] = str(e)
            logger.error(f"HTML scraper failed for {source['name']}: {e}")

        self.log_scraper_run(source["url"], result["status"], result["schemes_found"])
        return result

    def _extract_scheme(self, element, source: dict) -> Optional[dict]:
        """Extract scheme from HTML element."""
        try:
            name = ""
            link = element if element.name == "a" else element.find("a")
            heading = element.find(["h1", "h2", "h3", "h4", "h5"])

            if heading:
                name = heading.get_text(strip=True)
            elif link:
                name = link.get_text(strip=True)
            else:
                name = element.get_text(strip=True)[:100]

            if not name or len(name) < 5:
                return None

            desc_el = element.find("p")
            description = desc_el.get_text(strip=True)[:1000] if desc_el else ""

            url = ""
            if link and link.get("href"):
                href = link["href"]
                url = href if href.startswith("http") else f"{source['url'].rstrip('/')}/{href.lstrip('/')}"

            name_lower = source.get("name", "").lower()
            state = "Central"
            for key, val in {"tamil": "Tamil Nadu", "kerala": "Kerala", "andhra": "Andhra Pradesh"}.items():
                if key in name_lower:
                    state = val
                    break

            return {
                "name": name,
                "slug": self.generate_slug(name),
                "description": description,
                "state": state,
                "source_url": url or source["url"],
                "source_type": "html",
                "ministry": source.get("name", ""),
            }
        except Exception:
            return None


# --- Singletons ---
_myscheme_scraper: MySchemeAPIScraper | None = None
_selenium_scraper: SeleniumPortalScraper | None = None
_html_scraper: HTMLPortalScraper | None = None


def get_myscheme_scraper() -> MySchemeAPIScraper:
    global _myscheme_scraper
    if _myscheme_scraper is None:
        _myscheme_scraper = MySchemeAPIScraper()
    return _myscheme_scraper


def get_selenium_scraper() -> SeleniumPortalScraper:
    global _selenium_scraper
    if _selenium_scraper is None:
        _selenium_scraper = SeleniumPortalScraper()
    return _selenium_scraper


def get_html_scraper() -> HTMLPortalScraper:
    global _html_scraper
    if _html_scraper is None:
        _html_scraper = HTMLPortalScraper()
    return _html_scraper
