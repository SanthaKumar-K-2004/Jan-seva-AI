"""
Jan-Seva AI — Scheduler (Enhanced)
5 cron jobs for comprehensive data collection:
  1. Daily gazette scan (2 AM IST)
  2. Portal scan every 6 hours
  3. News feed monitoring (hourly)
  4. Wikipedia enrichment (weekly)
  5. News API scan (every 4 hours)
"""

import json
import os
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.utils.logger import logger


scheduler = AsyncIOScheduler()


def _load_targets():
    """Load scraper targets from JSON file."""
    targets_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "data", "scraper_targets.json"
    )
    if os.path.exists(targets_path):
        with open(targets_path, "r") as f:
            return json.load(f)
    return {"tier1": [], "tier2": [], "tier3": []}


# ═══════════════════════════════════════════
# JOB 1: Daily Gazette Scan (2 AM IST)
# ═══════════════════════════════════════════
async def daily_gazette_scan():
    """Download PDFs from gazette sites, OCR, chunk, and embed."""
    from app.services.scraper.gazette_scraper import get_gazette_scraper

    logger.info("📰 [Scheduler] Starting daily gazette scan...")
    scraper = get_gazette_scraper()
    targets = _load_targets()

    gazette_sources = [
        s for tier in targets.values()
        for s in (tier if isinstance(tier, list) else [])
        if s.get("type") in ("gazette", "pdf")
    ]

    results = []
    for source in gazette_sources:
        try:
            result = await scraper.scrape(source)
            results.append(result)
            logger.info(f"  ✅ {source['name']}: {result.get('schemes_found', 0)} schemes")
        except Exception as e:
            logger.error(f"  ❌ {source['name']}: {e}")

    total = sum(r.get("schemes_found", 0) for r in results)
    logger.info(f"📰 Gazette scan complete: {total} schemes from {len(results)} sources")


# ═══════════════════════════════════════════
# JOB 2: Portal Scan (Every 6 hours)
# ═══════════════════════════════════════════
async def portal_scan():
    """Scrape government portals using API/Selenium/HTML strategies."""
    from app.services.scraper.portal_scraper import get_myscheme_scraper, get_html_scraper

    logger.info("🌐 [Scheduler] Starting portal scan...")
    targets = _load_targets()

    portal_sources = [
        s for tier in targets.values()
        for s in (tier if isinstance(tier, list) else [])
        if s.get("type") in ("portal", "API", "html", "api")
    ]

    results = []
    for source in portal_sources[:10]:
        try:
            if "myscheme" in source.get("url", "").lower():
                scraper = get_myscheme_scraper()
            else:
                scraper = get_html_scraper()

            result = await scraper.scrape(source)
            results.append(result)
            logger.info(f"  ✅ {source['name']}: {result.get('schemes_found', 0)} schemes")
        except Exception as e:
            logger.error(f"  ❌ {source['name']}: {e}")

    total = sum(r.get("schemes_found", 0) for r in results)
    logger.info(f"🌐 Portal scan complete: {total} schemes from {len(results)} sources")


# ═══════════════════════════════════════════
# JOB 3: News RSS Monitor (Hourly)
# ═══════════════════════════════════════════
async def news_feed_monitor():
    """Monitor RSS feeds for scheme-related news."""
    from app.services.scraper.news_monitor import get_news_monitor

    logger.info("📡 [Scheduler] Starting news feed monitor...")
    monitor = get_news_monitor()

    targets = _load_targets()
    rss_sources = [
        s for tier in targets.values()
        for s in (tier if isinstance(tier, list) else [])
        if s.get("type") in ("RSS", "rss")
    ]

    results = []
    for source in rss_sources:
        try:
            result = await monitor.scrape(source)
            results.append(result)
            logger.info(f"  ✅ {source['name']}: {result.get('entries_found', 0)} entries")
        except Exception as e:
            logger.error(f"  ❌ {source['name']}: {e}")

    logger.info(f"📡 News monitor complete: {len(results)} feeds scanned")


# ═══════════════════════════════════════════
# JOB 4: Wikipedia Enrichment (Weekly)
# ═══════════════════════════════════════════
async def wikipedia_enrichment():
    """Enrich scheme data with Wikipedia descriptions and context."""
    from app.services.scraper.wikipedia_scraper import get_wikipedia_scraper

    logger.info("📚 [Scheduler] Starting Wikipedia enrichment...")
    scraper = get_wikipedia_scraper()

    try:
        result = await scraper.scrape({"name": "Wikipedia", "url": "https://en.wikipedia.org"})
        logger.info(
            f"📚 Wikipedia enrichment complete: "
            f"{result.get('schemes_found', 0)} new, "
            f"{result.get('schemes_enriched', 0)} enriched"
        )
    except Exception as e:
        logger.error(f"📚 Wikipedia enrichment failed: {e}")


# ═══════════════════════════════════════════
# JOB 5: News API Scan (Every 4 hours)
# ═══════════════════════════════════════════
async def news_api_scan():
    """Search news APIs for scheme-related articles."""
    from app.services.scraper.news_api_scraper import get_news_api_scraper
    from app.config import get_settings

    logger.info("🗞️ [Scheduler] Starting News API scan...")
    settings = get_settings()
    scraper = get_news_api_scraper(api_key=settings.news_api_key)

    try:
        result = await scraper.scrape({"name": "News API", "url": "https://newsapi.org"})
        logger.info(
            f"🗞️ News API scan complete: "
            f"{result.get('articles_found', 0)} articles, "
            f"{result.get('schemes_found', 0)} scheme-related"
        )
    except Exception as e:
        logger.error(f"🗞️ News API scan failed: {e}")


# ═══════════════════════════════════════════
# SCHEDULER LIFECYCLE
# ═══════════════════════════════════════════
def start_scheduler():
    """Start all scheduled jobs."""
    if scheduler.running:
        return

    # Job 1: Daily gazette (2 AM IST = 20:30 UTC previous day)
    scheduler.add_job(
        daily_gazette_scan,
        CronTrigger(hour=20, minute=30),
        id="daily_gazette",
        name="Daily Gazette Scan",
        replace_existing=True,
    )

    # Job 2: Portal scan every 6 hours
    scheduler.add_job(
        portal_scan,
        IntervalTrigger(hours=6),
        id="portal_scan",
        name="Portal Scan (6-hourly)",
        replace_existing=True,
    )

    # Job 3: News RSS monitor every hour
    scheduler.add_job(
        news_feed_monitor,
        IntervalTrigger(hours=1),
        id="news_monitor",
        name="News Feed Monitor (hourly)",
        replace_existing=True,
    )

    # Job 4: Wikipedia enrichment weekly (Sunday 3 AM IST)
    scheduler.add_job(
        wikipedia_enrichment,
        CronTrigger(day_of_week="sun", hour=21, minute=30),
        id="wikipedia_enrichment",
        name="Wikipedia Enrichment (weekly)",
        replace_existing=True,
    )

    # Job 5: News API every 4 hours
    scheduler.add_job(
        news_api_scan,
        IntervalTrigger(hours=4),
        id="news_api_scan",
        name="News API Scan (4-hourly)",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(
        "⏰ Scheduler started with 5 jobs:\n"
        "  📰 Gazette scan — daily 2:00 AM IST\n"
        "  🌐 Portal scan — every 6 hours\n"
        "  📡 News RSS — every 1 hour\n"
        "  📚 Wikipedia — weekly (Sunday 3 AM IST)\n"
        "  🗞️ News API — every 4 hours"
    )


def stop_scheduler():
    """Stop the scheduler."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("⏰ Scheduler stopped.")


def get_scheduler_status() -> dict:
    """Get current scheduler status and job info."""
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": str(job.next_run_time) if job.next_run_time else None,
            "trigger": str(job.trigger),
        })

    return {
        "running": scheduler.running,
        "jobs": jobs,
        "job_count": len(jobs),
    }
