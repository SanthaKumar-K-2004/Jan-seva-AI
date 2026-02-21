"""
Jan-Seva AI — Eligibility API Router (API-Only)
Check scheme eligibility using AI-powered analysis.
No database — uses live API research to determine eligibility.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from app.services.api_aggregator import get_api_aggregator
from app.utils.logger import logger

router = APIRouter()


class EligibilityRequest(BaseModel):
    scheme_name: str
    age: Optional[int] = None
    gender: Optional[str] = None
    income: Optional[float] = None
    caste_category: Optional[str] = None
    state: Optional[str] = None
    occupation: Optional[str] = None
    disability: Optional[bool] = None


@router.post("/check")
async def check_eligibility(request: EligibilityRequest):
    """
    Check if a user is eligible for a specific scheme.
    Uses AI research to analyze official eligibility criteria.
    """
    profile_parts = []
    if request.age:
        profile_parts.append(f"age {request.age}")
    if request.gender:
        profile_parts.append(f"gender {request.gender}")
    if request.income:
        profile_parts.append(f"annual income ₹{request.income:,.0f}")
    if request.caste_category:
        profile_parts.append(f"caste category {request.caste_category}")
    if request.state:
        profile_parts.append(f"residing in {request.state}")
    if request.occupation:
        profile_parts.append(f"occupation: {request.occupation}")
    if request.disability:
        profile_parts.append("person with disability")

    profile_desc = ", ".join(profile_parts) if profile_parts else "an Indian citizen"

    query = (
        f"Check eligibility for {request.scheme_name} scheme for a person who is {profile_desc}. "
        f"Provide: 1) Official eligibility criteria, 2) Whether this person qualifies (YES/NO with reason), "
        f"3) Required documents, 4) How to apply, 5) Official portal link."
    )

    aggregator = get_api_aggregator()
    result = await aggregator.query(user_query=query, language="en")

    return {
        "scheme": request.scheme_name,
        "profile": request.model_dump(exclude_none=True),
        "analysis": result["answer"],
        "sources": result.get("sources", []),
    }


@router.get("/criteria/{scheme_name}")
async def get_eligibility_criteria(scheme_name: str):
    """Get detailed eligibility criteria for a scheme."""
    aggregator = get_api_aggregator()
    query = (
        f"What are the complete, detailed eligibility criteria for the {scheme_name} scheme? "
        f"Include: age limits, income limits, caste/category requirements, "
        f"geographic requirements, occupation requirements, and any other conditions."
    )

    result = await aggregator.query(user_query=query, language="en")

    return {
        "scheme": scheme_name,
        "criteria": result["answer"],
        "sources": result.get("sources", []),
    }
