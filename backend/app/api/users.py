"""
Jan-Seva AI — Users API Router (API-Only)
In-memory user profiles — no database.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from app.utils.logger import logger

router = APIRouter()

# In-memory user store (ephemeral)
_users = {}


class UserProfile(BaseModel):
    phone: str
    name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    state: Optional[str] = None
    income: Optional[float] = None
    caste_category: Optional[str] = None
    occupation: Optional[str] = None


@router.post("/register")
async def register_user(user: UserProfile):
    """Create or update a citizen profile (in-memory)."""
    _users[user.phone] = user.model_dump()
    logger.info(f"👤 User registered: {user.phone}")
    return {"status": "registered", "user": _users[user.phone]}


@router.get("/{phone}")
async def get_user(phone: str):
    """Get user profile."""
    user = _users.get(phone)
    if not user:
        return {"error": "User not found", "phone": phone}
    return {"user": user}


@router.get("/{phone}/matches")
async def get_user_matches(phone: str):
    """Find matching schemes for a registered user."""
    user = _users.get(phone)
    if not user:
        return {"error": "User not found. Please register first."}

    from app.services.api_aggregator import get_api_aggregator

    profile_parts = []
    if user.get("age"):
        profile_parts.append(f"age {user['age']}")
    if user.get("gender"):
        profile_parts.append(f"gender {user['gender']}")
    if user.get("income"):
        profile_parts.append(f"annual income ₹{user['income']:,.0f}")
    if user.get("caste_category"):
        profile_parts.append(f"caste category {user['caste_category']}")
    if user.get("state"):
        profile_parts.append(f"from {user['state']}")
    if user.get("occupation"):
        profile_parts.append(f"occupation: {user['occupation']}")

    profile_desc = ", ".join(profile_parts) if profile_parts else "an Indian citizen"
    query = f"Find all eligible government schemes for a person who is {profile_desc}."

    aggregator = get_api_aggregator()
    result = await aggregator.query(user_query=query, language="en")

    return {
        "phone": phone,
        "matches": result["answer"],
        "sources": result.get("sources", []),
    }
