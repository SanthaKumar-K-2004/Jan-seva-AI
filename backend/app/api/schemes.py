"""
Jan-Seva AI — Schemes API Router (API-Only)
Search and discover government schemes through live API calls.
No database — all data sourced from search APIs and AI research.
"""

from fastapi import APIRouter, Query
from typing import Optional
from app.services.api_aggregator import get_api_aggregator
from app.utils.logger import logger

router = APIRouter()


@router.get("/")
async def list_schemes(
    state: Optional[str] = Query(None, description="Filter by state"),
    category: Optional[str] = Query(None, description="Filter by category (e.g., education, health, agriculture)"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """
    Discover government schemes via live API search.
    Searches multiple sources and returns AI-curated results.
    """
    query_parts = ["government schemes India"]
    if state:
        query_parts.append(f"in {state}")
    if category:
        query_parts.append(f"for {category}")

    search_query = " ".join(query_parts)

    aggregator = get_api_aggregator()
    result = await aggregator.query(
        user_query=search_query,
        language="en",
    )

    return {
        "answer": result["answer"],
        "sources": result.get("sources", []),
        "images": result.get("images", []),
        "query": search_query,
        "filters": {"state": state, "category": category},
    }


@router.get("/search")
async def search_schemes(q: str = Query(..., description="Search query")):
    """Search for government schemes using multi-API aggregation."""
    aggregator = get_api_aggregator()
    result = await aggregator.query(
        user_query=q,
        language="en",
    )
    return {
        "query": q,
        "answer": result["answer"],
        "sources": result.get("sources", []),
        "images": result.get("images", []),
        "providers_used": result.get("providers_queried", []),
    }


@router.get("/{scheme_name}")
async def get_scheme(scheme_name: str):
    """
    Get detailed information about a specific scheme via AI research.
    Pass the scheme name (e.g., "PM-KISAN", "Ayushman-Bharat").
    """
    aggregator = get_api_aggregator()
    detailed_query = (
        f"Provide complete details about the {scheme_name} government scheme: "
        f"eligibility criteria, benefits amount, documents required, "
        f"how to apply, official portal link, and current status."
    )

    result = await aggregator.query(
        user_query=detailed_query,
        language="en",
    )

    return {
        "scheme_name": scheme_name,
        "details": result["answer"],
        "sources": result.get("sources", []),
        "images": result.get("images", []),
    }


@router.post("/match")
async def match_schemes(
    age: Optional[int] = None,
    gender: Optional[str] = None,
    income: Optional[float] = None,
    caste_category: Optional[str] = None,
    state: Optional[str] = None,
):
    """
    Find matching schemes for a user profile using AI-powered matching.
    No database — uses live research to find relevant schemes.
    """
    profile_parts = []
    if age:
        profile_parts.append(f"age {age}")
    if gender:
        profile_parts.append(f"gender {gender}")
    if income:
        profile_parts.append(f"annual income ₹{income:,.0f}")
    if caste_category:
        profile_parts.append(f"caste category {caste_category}")
    if state:
        profile_parts.append(f"from {state}")

    profile_desc = ", ".join(profile_parts) if profile_parts else "an Indian citizen"

    query = (
        f"Find all eligible government schemes for a person who is {profile_desc}. "
        f"List each scheme with exact eligibility criteria, benefits, and how to apply."
    )

    aggregator = get_api_aggregator()
    result = await aggregator.query(user_query=query, language="en")

    return {
        "profile": {
            "age": age, "gender": gender, "income": income,
            "caste_category": caste_category, "state": state,
        },
        "matches": result["answer"],
        "sources": result.get("sources", []),
        "total_sources": len(result.get("sources", [])),
    }
