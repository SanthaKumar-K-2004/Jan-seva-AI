"""
Jan-Seva AI - Admin API Router (API-Only)
Admin tools: system health, analytics, and operational helpers.
"""

from typing import Any, Dict, Optional, Tuple

from fastapi import APIRouter, Query

from app.config import get_settings
from app.core.supabase_client import get_supabase_client
from app.utils.logger import logger

router = APIRouter()


def _has_supabase_config() -> bool:
    settings = get_settings()
    return bool(settings.supabase_url and (settings.supabase_service_role_key or settings.supabase_anon_key))


def _safe_table_count(client: Any, table_name: str) -> Optional[int]:
    try:
        response = client.table(table_name).select("id", count="exact").limit(1).execute()
        if response.count is not None:
            return int(response.count)
        return len(response.data or [])
    except Exception as exc:
        logger.warning(f"Admin count skipped for table '{table_name}': {exc}")
        return None


def _first_available_count(client: Any, table_names: list[str], default: int = 0) -> int:
    for table_name in table_names:
        count = _safe_table_count(client, table_name)
        if count is not None:
            return count
    return default


def _fetch_admin_schemes(
    client: Any,
    page: int,
    limit: int,
    search: Optional[str],
) -> Tuple[list[Dict[str, Any]], int]:
    start = (page - 1) * limit
    end = start + limit - 1

    query = client.table("schemes").select(
        "id, name, ministry, state, category, updated_at",
        count="exact",
    )

    if search:
        query = query.ilike("name", f"%{search}%")

    response = query.order("updated_at", desc=True).range(start, end).execute()
    return response.data or [], int(response.count or 0)


@router.get("/status")
async def api_status():
    """Check status of configured API integrations."""
    settings = get_settings()

    return {
        "apis": {
            "groq_llm": {
                "configured": bool(settings.groq_api_key),
                "keys_available": len(settings.all_groq_keys),
            },
            "google_gemini": {
                "configured": bool(settings.google_api_key),
                "keys_available": len(settings.all_google_keys),
            },
            "nvidia_qwen": {
                "configured": bool(settings.nvidia_api_key),
            },
            "tavily_search": {
                "configured": bool(settings.tavily_api_key),
            },
            "news_api": {
                "configured": bool(settings.news_api_key),
            },
            "wikipedia": {
                "configured": bool(settings.wikipedia_access_token),
            },
            "duckduckgo": {
                "configured": True,  # No API key needed
            },
            "bhashini_translation": {
                "configured": bool(settings.bhashini_api_key),
            },
            "whatsapp": {
                "configured": bool(settings.whatsapp_access_token),
            },
        },
        "environment": settings.app_env,
    }


@router.get("/analytics")
async def admin_analytics():
    """
    Dashboard analytics payload expected by the frontend admin dashboard.
    Returns safe fallback values when Supabase is not configured.
    """
    fallback = {
        "total_schemes": 0,
        "total_users": 0,
        "total_chats": 0,
        "active_sos": 0,
        "source": "fallback",
    }

    if not _has_supabase_config():
        return {
            **fallback,
            "message": "Supabase is not configured; returning fallback analytics.",
        }

    try:
        client = get_supabase_client()
    except Exception as exc:
        logger.warning(f"Admin analytics fallback (supabase init failed): {exc}")
        return {
            **fallback,
            "message": "Supabase client unavailable; returning fallback analytics.",
        }

    return {
        "total_schemes": _first_available_count(client, ["schemes"]),
        "total_users": _first_available_count(client, ["users", "citizens", "profiles"]),
        "total_chats": _first_available_count(client, ["chat_history", "chats"]),
        "active_sos": _first_available_count(client, ["sos_alerts", "alerts", "emergency_alerts"]),
        "source": "supabase",
    }


@router.get("/schemes")
async def admin_schemes(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, min_length=1),
):
    """
    Lightweight scheme list for Admin CMS.
    Uses Supabase when configured, otherwise returns an empty valid response.
    """
    fallback = {
        "schemes": [],
        "page": page,
        "limit": limit,
        "total": 0,
        "source": "fallback",
    }

    if not _has_supabase_config():
        return {
            **fallback,
            "message": "Supabase is not configured; no CMS scheme data available.",
        }

    try:
        client = get_supabase_client()
        schemes, total = _fetch_admin_schemes(client, page=page, limit=limit, search=search)
        return {
            "schemes": schemes,
            "page": page,
            "limit": limit,
            "total": total,
            "source": "supabase",
        }
    except Exception as exc:
        logger.warning(f"Admin schemes fallback: {exc}")
        return {
            **fallback,
            "message": "Failed to fetch schemes from Supabase; returning fallback payload.",
        }


@router.post("/test-search")
async def test_search(query: str = "PM Kisan Samman Nidhi scheme"):
    """Test all search providers and return raw results for diagnostics."""
    from app.services.providers.ddg_provider import DuckDuckGoProvider
    from app.services.providers.news_provider import NewsProvider
    from app.services.providers.tavily_provider import TavilyProvider
    from app.services.providers.wikipedia_provider import WikipediaProvider

    providers = {
        "tavily": TavilyProvider(),
        "ddg": DuckDuckGoProvider(),
        "wikipedia": WikipediaProvider(),
        "news": NewsProvider(),
    }

    tasks = {name: provider.search(query, max_results=3) for name, provider in providers.items()}
    results: Dict[str, Any] = {}

    for name, task in tasks.items():
        try:
            resp = await task
            results[name] = {
                "success": resp.success,
                "result_count": len(resp.results),
                "latency_ms": round(resp.latency_ms),
                "results": [
                    {"title": r.title, "url": r.url, "score": r.score}
                    for r in resp.results[:3]
                ],
                "error": resp.error,
            }
        except Exception as exc:
            results[name] = {"success": False, "error": str(exc)}

    return {"query": query, "providers": results}
