"""
Jan-Seva AI — Scraper Package
Exports all scraper classes and their singleton getters.
"""

from app.services.scraper.gazette_scraper import GazetteScraper, get_gazette_scraper
from app.services.scraper.portal_scraper import (
    MySchemeAPIScraper,
    SeleniumPortalScraper,
    HTMLPortalScraper,
    get_myscheme_scraper,
    get_selenium_scraper,
    get_html_scraper,
)
from app.services.scraper.news_monitor import NewsMonitor, get_news_monitor
from app.services.scraper.wikipedia_scraper import WikipediaScraper, get_wikipedia_scraper
from app.services.scraper.news_api_scraper import NewsAPIScraper, get_news_api_scraper
