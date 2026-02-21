"""
Jan-Seva AI — Pydantic Models for Chat & Eligibility
"""

from pydantic import BaseModel
from typing import Optional


class ChatTextRequest(BaseModel):
    """Text chat request."""
    message: str
    user_id: Optional[str] = None
    language: str = "en"              # ISO 639-1 code (en, hi, ta, te, bn, etc.)
    conversation_id: Optional[str] = None  # For continuing conversations
    session_id: Optional[str] = None      # Alias for conversation_id; used for session tracking
    user_state: Optional[str] = None      # Client-supplied state override ("TN", "MH", etc.)
    ip_address: Optional[str] = None      # Client IP (auto-extracted by chat.py if not set)


class ChatAudioRequest(BaseModel):
    """Audio chat metadata (file uploaded separately via multipart)."""
    user_id: Optional[str] = None
    language: str = "auto"           # auto-detect from audio
    slow: bool = False               # Slow mode for elderly users
    session_id: Optional[str] = None
    user_state: Optional[str] = None


class SchemeReference(BaseModel):
    """A scheme reference returned in chat responses."""
    id: Optional[str] = None
    name: str
    benefits: str = ""


class ChatResponse(BaseModel):
    """Chat response model."""
    reply: str
    sources: list[dict] = []
    images: list[str] = []
    language: str = "en"
    audio_url: Optional[str] = None
    schemes: list[dict] = []         # Related schemes found
    transcribed_text: Optional[str] = None  # For audio responses
    warning_count: Optional[int] = None     # Set when an off-topic warning was issued
    is_blocked: bool = False                # True when user is currently blocked


class EligibilityRequest(BaseModel):
    """Request to check eligibility for a scheme."""
    user_id: Optional[str] = None
    scheme_id: Optional[str] = None
    # Direct profile (if user_id not provided)
    age: Optional[int] = None
    gender: Optional[str] = None
    income: Optional[float] = None
    caste_category: Optional[str] = None
    occupation: Optional[str] = None
    state: Optional[str] = None
    education: Optional[str] = None
    disability: Optional[str] = None
    marital_status: Optional[str] = None
    landholding: Optional[float] = None  # in acres
    family_size: Optional[int] = None


class EligibilityResponse(BaseModel):
    """Eligibility check result."""
    scheme_id: str
    scheme_name: str
    is_eligible: bool
    match_score: int = 0  # 0-100
    reason: str
    missing_criteria: list[str] = []
    alternatives: list[dict] = []  # Similar schemes they ARE eligible for
