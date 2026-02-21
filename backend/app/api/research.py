"""
Jan-Seva AI — Research API Router (API-Only)
Deep research using all available API providers.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from app.services.api_aggregator import get_api_aggregator
from app.utils.logger import logger

router = APIRouter()


class ResearchRequest(BaseModel):
    query: str
    language: str = "en"
    user_profile: Optional[Dict[str, Any]] = None


@router.post("/ask")
async def research_scheme(request: ResearchRequest):
    """
    Deep research using all API providers simultaneously.
    Returns a synthesized expert response + sources + images.
    """
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    # Add user profile context to query if provided
    query = request.query
    if request.user_profile:
        profile_parts = []
        for key, value in request.user_profile.items():
            if value:
                profile_parts.append(f"{key}: {value}")
        if profile_parts:
            query += f" (User profile: {', '.join(profile_parts)})"

    aggregator = get_api_aggregator()
    result = await aggregator.query(
        user_query=query,
        language=request.language,
    )

    return {
        "answer": result["answer"],
        "sources": result.get("sources", []),
        "images": result.get("images", []),
        "providers_used": result.get("providers_queried", []),
    }
