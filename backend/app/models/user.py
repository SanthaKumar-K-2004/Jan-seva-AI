"""
Jan-Seva AI — Pydantic Models for Users & Family
"""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class UserProfile(BaseModel):
    """Citizen profile for eligibility checking."""
    phone: Optional[str] = None
    name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    income: Optional[float] = None
    caste_category: Optional[str] = None  # General, OBC, SC, ST
    occupation: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    preferred_language: str = "en"
    
    # Extended fields for matching
    is_student: bool = False
    is_farmer: bool = False
    is_disabled: bool = False
    marital_status: Optional[str] = None  # Single, Married, Widowed, Divorced


class UserCreate(UserProfile):
    """Model for creating/registering a user."""
    pass


class UserResponse(UserProfile):
    """Model returned from API."""
    id: str
    created_at: datetime

    class Config:
        from_attributes = True


class FamilyMember(BaseModel):
    """Family member for family-wide scheme matching."""
    relation: str  # spouse, child, parent
    age: Optional[int] = None
    gender: Optional[str] = None
    occupation: Optional[str] = None


class FamilyMemberCreate(FamilyMember):
    """Model for adding a family member."""
    user_id: str
