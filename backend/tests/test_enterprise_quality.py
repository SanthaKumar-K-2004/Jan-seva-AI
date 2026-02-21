from datetime import datetime, timedelta, timezone

from app.config import get_settings
from app.services.providers.base import SearchResult
from app.services.quality_scorer import get_quality_scorer
from app.services.research_cache import ResearchCache


def _iso(days_ago: int) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def test_openai_key_aggregation_and_dedup(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k1")
    monkeypatch.setenv("OPENAI_API_KEY_2", "k2")
    monkeypatch.setenv("OPENAI_API_KEY_3", "k1")
    monkeypatch.setenv("OPENAI_API_KEYS_CSV", "k3,k2,k4")

    get_settings.cache_clear()
    settings = get_settings()
    assert settings.all_openai_keys == ["k1", "k2", "k3", "k4"]

    get_settings.cache_clear()


def test_verified_filter_news_is_recent_and_trusted():
    scorer = get_quality_scorer()

    results = [
        SearchResult(
            title="Trusted and recent",
            url="https://pib.gov.in/pressrelease",
            content="Recent official update",
            domain="pib.gov.in",
            published_date=_iso(1),
            source_name="NewsAPI",
        ),
        SearchResult(
            title="Trusted but stale",
            url="https://thehindu.com/old-update",
            content="Old update",
            domain="thehindu.com",
            published_date=_iso(60),
            source_name="NewsAPI",
        ),
        SearchResult(
            title="Fresh but low trust",
            url="https://example-blog.net/post",
            content="Unverified post",
            domain="example-blog.net",
            published_date=_iso(1),
            source_name="DuckDuckGo",
        ),
    ]

    filtered = scorer.filter_verified_results(
        results,
        query_intent="latest_news",
        min_reliability=0.67,
        max_age_days=45,
        max_news_age_days=7,
    )
    assert len(filtered) == 1
    assert filtered[0].domain == "pib.gov.in"


def test_verified_filter_accepts_gov_without_date():
    scorer = get_quality_scorer()
    results = [
        SearchResult(
            title="Official portal page",
            url="https://myscheme.gov.in/scheme",
            content="Scheme details",
            domain="myscheme.gov.in",
            published_date=None,
            source_name="Tavily",
        )
    ]

    filtered = scorer.filter_verified_results(
        results,
        query_intent="scheme_discovery",
        min_reliability=0.67,
        max_age_days=45,
        max_news_age_days=7,
    )
    assert len(filtered) == 1
    assert filtered[0].domain == "myscheme.gov.in"


def test_research_cache_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("RESEARCH_CACHE_ENABLED", "true")
    monkeypatch.setenv("RESEARCH_CACHE_TTL_MINUTES", "10")
    monkeypatch.setenv("RESEARCH_CACHE_PATH", str(tmp_path / "research_cache.sqlite3"))

    get_settings.cache_clear()
    cache = ResearchCache()

    payload = {
        "answer": "Test answer",
        "sources": [{"url": "https://myscheme.gov.in"}],
        "language": "en",
    }
    cache.put(
        query="PM Kisan update",
        language="en",
        intent="latest_news",
        state_code="TN",
        payload=payload,
    )

    loaded = cache.get(
        query="PM Kisan update",
        language="en",
        intent="latest_news",
        state_code="TN",
    )
    assert loaded is not None
    assert loaded["answer"] == "Test answer"

    get_settings.cache_clear()
