"""
Jan-Seva AI — Analytics API Router (API-Only)
Scheme comparison and gap analysis using live research.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from app.services.api_aggregator import get_api_aggregator
from app.utils.logger import logger

router = APIRouter()


class ComparisonRequest(BaseModel):
    scheme_names: List[str]


class GapAnalysisRequest(BaseModel):
    sector: str
    state: str


@router.post("/compare")
async def compare_schemes(request: ComparisonRequest):
    """Compare multiple government schemes side-by-side."""
    if len(request.scheme_names) < 2:
        raise HTTPException(status_code=400, detail="At least 2 schemes required for comparison.")

    schemes_list = ", ".join(request.scheme_names)
    query = (
        f"Create a detailed side-by-side comparison of these government schemes: {schemes_list}. "
        f"Compare: eligibility criteria, benefits amount, target beneficiaries, "
        f"application process, documents required, and official websites. "
        f"Present in a clear markdown table format."
    )

    aggregator = get_api_aggregator()
    result = await aggregator.query(user_query=query, language="en")

    return {
        "schemes_compared": request.scheme_names,
        "report": result["answer"],
        "sources": result.get("sources", []),
    }


@router.post("/gap-analysis")
async def analyze_gaps(request: GapAnalysisRequest):
    """Identify coverage gaps in government schemes for a sector/state."""
    query = (
        f"Analyze the coverage gaps in government schemes for the {request.sector} sector "
        f"in {request.state}, India. Identify: "
        f"1) What schemes exist, 2) What demographics are underserved, "
        f"3) What benefits are missing compared to other states, "
        f"4) Recommendations for improvement."
    )

    aggregator = get_api_aggregator()
    result = await aggregator.query(user_query=query, language="en")

    return {
        "sector": request.sector,
        "state": request.state,
        "insights": result["answer"],
        "sources": result.get("sources", []),
    }
