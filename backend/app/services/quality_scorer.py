"""
Jan-Seva AI — Quality Scorer v2
Scores and ranks API results by relevance, recency, and reliability.
Extended with Indian state government portals and scheme-specific domains.
"""

import re
from datetime import datetime, timezone
from app.services.providers.base import SearchResult
from app.utils.logger import logger


# Domain trust rankings (higher = more reliable)
DOMAIN_TRUST = {
    # Central Government (highest trust)
    "myscheme.gov.in": 1.0,
    "india.gov.in": 1.0,
    "pmkisan.gov.in": 1.0,
    "pmjay.gov.in": 1.0,
    "nrega.nic.in": 1.0,
    "pmayg.nic.in": 1.0,
    "pmaymis.gov.in": 1.0,
    "pib.gov.in": 0.97,
    "nic.in": 0.97,

    # State Government TN
    "tn.gov.in": 1.0,
    "tahdco.tn.gov.in": 1.0,
    "tnau.ac.in": 0.97,
    "sipcot.com": 0.95,
    "tnsocialwelfare.tn.gov.in": 0.97,
    "tnschemes.tn.gov.in": 1.0,

    # State Government AP/TS
    "ap.gov.in": 1.0,
    "ts.gov.in": 1.0,
    "tsiic.telangana.gov.in": 0.95,

    # State Government KA/KL
    "karnataka.gov.in": 1.0,
    "kerala.gov.in": 1.0,
    "sevasindhu.karnataka.gov.in": 0.97,

    # State Government MH/GJ
    "maharashtra.gov.in": 1.0,
    "mahadbt.maharashtra.gov.in": 0.97,
    "gujarat.gov.in": 1.0,

    # State Government UP/BR
    "up.gov.in": 1.0,
    "bihar.gov.in": 1.0,
    "sspy-up.gov.in": 0.97,

    # State Government WB/OD
    "wb.gov.in": 1.0,
    "odisha.gov.in": 1.0,

    # State Government RJ/MP/CG
    "rajasthan.gov.in": 1.0,
    "mp.gov.in": 1.0,
    "cgstate.gov.in": 1.0,

    # General .gov.in TLD (catch-all for Indian government)
    ".gov.in": 1.0,
    ".nic.in": 0.97,

    # Knowledge bases
    "wikipedia.org": 0.80,
    "britannica.com": 0.80,

    # News & media (reputable Indian)
    "thehindu.com": 0.72,
    "ndtv.com": 0.70,
    "livemint.com": 0.70,
    "economictimes.com": 0.70,
    "hindustantimes.com": 0.67,
    "timesofindia.com": 0.67,
    "moneycontrol.com": 0.65,
    "businessstandard.com": 0.70,
    "financialexpress.com": 0.68,
    "news18.com": 0.63,

    # AI / research
    "nvidia.com": 0.75,
    "google.com": 0.75,

    # Default
    "_default": 0.40,
}


class QualityScorer:
    """
    Scores search results using a weighted formula:
    Quality = (Relevance × 0.4) + (Recency × 0.3) + (Reliability × 0.3)
    """

    def score_results(
        self,
        results: list[SearchResult],
        query: str,
        top_k: int = 12,
    ) -> list[SearchResult]:
        """Score, rank, and return top-K results."""
        if not results:
            return []

        scored = []
        for result in results:
            relevance = self._relevance_score(result, query)
            recency = self._recency_score(result)
            reliability = self._reliability_score(result)

            final_score = (relevance * 0.4) + (recency * 0.3) + (reliability * 0.3)
            result.score = round(final_score, 3)
            scored.append(result)

        # Sort by score descending
        scored.sort(key=lambda r: r.score, reverse=True)

        # Deduplicate by URL
        seen_urls = set()
        unique = []
        for r in scored:
            if r.url not in seen_urls:
                unique.append(r)
                seen_urls.add(r.url)

        top_results = unique[:top_k]
        logger.info(
            f"📊 Scored {len(results)} results → Top {len(top_results)} "
            f"(best: {top_results[0].score if top_results else 0})"
        )
        return top_results

    def domain_reliability(self, domain: str) -> float:
        """Return reliability score for a domain without modifying result objects."""
        if not domain:
            return DOMAIN_TRUST["_default"]

        domain = domain.lower()

        for trusted_domain, score in DOMAIN_TRUST.items():
            if trusted_domain.startswith("_"):
                continue
            if trusted_domain in domain:
                return score

        if domain.endswith(".gov.in") or domain.endswith(".nic.in"):
            return 1.0
        if domain.endswith(".gov"):
            return 0.9
        if domain.endswith(".edu") or domain.endswith(".ac.in"):
            return 0.85
        if domain.endswith(".org"):
            return 0.70
        return DOMAIN_TRUST["_default"]

    def filter_verified_results(
        self,
        results: list[SearchResult],
        query_intent: str | None = None,
        min_reliability: float = 0.67,
        max_age_days: int = 45,
        max_news_age_days: int = 21,
    ) -> list[SearchResult]:
        """
        Filter low-trust/stale results to enforce citation quality.
        """
        if not results:
            return []

        is_news_intent = (query_intent or "").lower() == "latest_news"
        limit_days = max_news_age_days if is_news_intent else max_age_days

        verified = []
        for result in results:
            reliability = self.domain_reliability(result.domain)
            if reliability < min_reliability:
                continue

            if not self._is_recent_enough(result, max_days=limit_days):
                continue

            verified.append(result)

        if not verified:
            logger.warning(
                "No results passed strict verification filter. "
                "Falling back to raw scoring candidates."
            )
        return verified

    def _parse_date(self, date_text: str | None) -> datetime | None:
        if not date_text:
            return None
        for fmt in [
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%S%z",
        ]:
            try:
                dt = datetime.strptime(date_text, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue
        return None

    def _is_recent_enough(self, result: SearchResult, max_days: int) -> bool:
        """
        Accept unknown publication dates for official government sources.
        """
        reliability = self.domain_reliability(result.domain)
        parsed = self._parse_date(result.published_date)

        if parsed is None:
            return reliability >= 0.95

        days_old = (datetime.now(timezone.utc) - parsed).days
        return days_old <= max_days

    def _relevance_score(self, result: SearchResult, query: str) -> float:
        """Keyword overlap + provider score."""
        query_words = set(re.findall(r"\b\w+\b", query.lower()))
        content_words = set(re.findall(r"\b\w+\b", (result.title + " " + result.content).lower()))

        if not query_words:
            return 0.5

        overlap = len(query_words & content_words) / len(query_words)

        # Blend with provider's own relevance score if available
        provider_score = result.score if result.score > 0 else 0.5
        return (overlap * 0.6) + (provider_score * 0.4)

    def _recency_score(self, result: SearchResult) -> float:
        """Score based on publication date. Newer = higher."""
        if not result.published_date:
            return 0.5  # Unknown date gets middle score

        try:
            pub_date = self._parse_date(result.published_date)

            if not pub_date:
                return 0.5

            now = datetime.now(timezone.utc)
            days_old = (now - pub_date).days

            if days_old <= 7:
                return 1.0
            elif days_old <= 30:
                return 0.9
            elif days_old <= 90:
                return 0.75
            elif days_old <= 365:
                return 0.5
            else:
                return 0.3

        except Exception:
            return 0.5

    def _reliability_score(self, result: SearchResult) -> float:
        """Score based on source domain trustworthiness."""
        return self.domain_reliability(result.domain)


# Singleton
_scorer = None

def get_quality_scorer() -> QualityScorer:
    global _scorer
    if _scorer is None:
        _scorer = QualityScorer()
    return _scorer
