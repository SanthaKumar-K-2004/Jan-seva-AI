"""
Jan-Seva AI — Session Store
In-memory store for:
- User profiles (age, income, caste, occupation, state, etc.)
- Off-topic warning counts
- Temporary 1-hour blocks for repeat offenders

All state is per session_id (conversation_id or user_id).
Resets on server restart (upgrade to Redis/Supabase for persistence).
"""

import time
from dataclasses import dataclass, field
from app.utils.logger import logger


BLOCK_DURATION_SECONDS = 3600  # 1 hour
MAX_WARNINGS = 3


@dataclass
class UserSession:
    """Holds everything known about a user within a session."""
    # ── Known user profile (filled progressively from conversation) ──
    state_code: str | None = None       # "TN", "MH", etc.
    state_name: str | None = None       # "Tamil Nadu"
    age: int | None = None
    gender: str | None = None
    income_per_year: float | None = None
    caste_category: str | None = None   # "General", "OBC", "SC", "ST", "EWS"
    occupation: str | None = None       # "farmer", "student", "daily wage", etc.
    education: str | None = None        # "10th", "12th", "graduate", etc.
    disability: str | None = None
    marital_status: str | None = None
    landholding_acres: float | None = None
    family_size: int | None = None
    bpl_card: bool | None = None
    # ── Moderation ──
    warnings: int = 0
    blocked_until: float = 0.0          # Unix timestamp; 0 = not blocked
    # ── Chat context ──
    chat_history: list = field(default_factory=list)


# Global store: session_id → UserSession
_sessions: dict[str, UserSession] = {}


def _get_or_create(session_id: str) -> UserSession:
    if session_id not in _sessions:
        _sessions[session_id] = UserSession()
    return _sessions[session_id]


# ──────────────────────────────────────────────────────────────
# Profile Management
# ──────────────────────────────────────────────────────────────

def get_profile(session_id: str) -> dict:
    """Return known user profile as a dict (only non-None keys)."""
    session = _get_or_create(session_id)
    profile = {}
    if session.state_name:
        profile["state"] = session.state_name
    if session.state_code:
        profile["state_code"] = session.state_code
    if session.age is not None:
        profile["age"] = session.age
    if session.gender:
        profile["gender"] = session.gender
    if session.income_per_year is not None:
        profile["income_per_year"] = session.income_per_year
    if session.caste_category:
        profile["caste_category"] = session.caste_category
    if session.occupation:
        profile["occupation"] = session.occupation
    if session.education:
        profile["education"] = session.education
    if session.disability:
        profile["disability"] = session.disability
    if session.marital_status:
        profile["marital_status"] = session.marital_status
    if session.landholding_acres is not None:
        profile["landholding_acres"] = session.landholding_acres
    if session.family_size is not None:
        profile["family_size"] = session.family_size
    if session.bpl_card is not None:
        profile["bpl_card"] = session.bpl_card
    return profile


def update_profile(session_id: str, updates: dict) -> None:
    """Merge new profile data into existing session."""
    session = _get_or_create(session_id)
    for key, value in updates.items():
        if value is not None and hasattr(session, key):
            setattr(session, key, value)
    logger.debug(f"👤 Profile updated for {session_id}: {updates}")


def set_state_from_ip(session_id: str, state_info: dict | None) -> None:
    """Set state from IP resolution (only if user hasn't set it themselves)."""
    if not state_info:
        return
    session = _get_or_create(session_id)
    # Don't overwrite if explicitly set by user
    if session.state_code is None:
        session.state_code = state_info.get("code")
        session.state_name = state_info.get("name")


# ──────────────────────────────────────────────────────────────
# Chat History
# ──────────────────────────────────────────────────────────────

def get_chat_history(session_id: str, last_n: int = 8) -> list:
    """Return recent chat history for LLM context."""
    session = _get_or_create(session_id)
    return session.chat_history[-last_n:]


def append_chat(session_id: str, role: str, content: str) -> None:
    """Append a message to the session's chat history."""
    session = _get_or_create(session_id)
    session.chat_history.append({"role": role, "content": content})
    # Keep only last 30 messages
    if len(session.chat_history) > 30:
        session.chat_history = session.chat_history[-30:]


# ──────────────────────────────────────────────────────────────
# Warning & Block System
# ──────────────────────────────────────────────────────────────

def is_blocked(session_id: str) -> tuple[bool, float]:
    """
    Returns (is_blocked, seconds_remaining).
    Automatically clears expired blocks.
    """
    session = _get_or_create(session_id)
    if session.blocked_until == 0:
        return False, 0.0
    remaining = session.blocked_until - time.time()
    if remaining <= 0:
        # Block expired — reset
        session.blocked_until = 0.0
        session.warnings = 0
        logger.info(f"🔓 Block expired for session {session_id}")
        return False, 0.0
    return True, remaining


def issue_warning(session_id: str) -> tuple[int, bool]:
    """
    Issue an off-topic warning. Returns (warning_number, is_now_blocked).
    At MAX_WARNINGS, applies a 1-hour block.
    """
    session = _get_or_create(session_id)
    session.warnings += 1
    warning_num = session.warnings

    if warning_num >= MAX_WARNINGS:
        session.blocked_until = time.time() + BLOCK_DURATION_SECONDS
        logger.warning(f"🚫 Session {session_id} BLOCKED for 1 hour (3 off-topic warnings)")
        return warning_num, True

    logger.info(f"⚠️ Warning {warning_num}/{MAX_WARNINGS} issued to session {session_id}")
    return warning_num, False


def get_warning_count(session_id: str) -> int:
    return _get_or_create(session_id).warnings


def clear_session(session_id: str) -> None:
    """Remove a session entirely (for testing or admin tools)."""
    _sessions.pop(session_id, None)
