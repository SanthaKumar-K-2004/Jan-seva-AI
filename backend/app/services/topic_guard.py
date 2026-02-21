"""
Jan-Seva AI — Topic Guard
Enforces that the AI only answers government scheme / citizen welfare related questions.
Fast rule-based classification — zero API calls, zero latency.

Returns one of three verdicts:
  ALLOWED  — proceed with full research pipeline
  WARN     — off-topic, issue warning to user
  BLOCK    — extreme / harmful content, hard block (no warning counter used)
"""

import re
from enum import Enum
from app.utils.logger import logger


class TopicVerdict(str, Enum):
    ALLOWED = "allowed"
    WARN = "warn"          # Off-topic (contributes to warning counter)
    BLOCK = "block"        # Abusive / extreme content (instant block message)


# ── On-Topic Keywords (scheme / citizen welfare domain) ──────────────────────
# If ANY of these appear in the query, it is definitely on-topic.
ON_TOPIC_KEYWORDS = {
    # Core scheme vocabulary
    "scheme", "yojana", "subsidy", "benefit", "pension", "scholarship",
    "stipend", "grant", "allowance", "welfare", "assistance", "relief",
    "compensation", "insurance", "loan", "incentive", "rebate",
    # Agricultural
    "farmer", "agriculture", "kisan", "krishi", "fasal", "crop",
    "irrigation", "soil", "fertilizer", "seed", "mandi", "pm-kisan",
    "pm kisan", "pradhan mantri kisan", "land", "patta", "chitta",
    "tahdco", "tnau", "sipcot", "agricultural", "horticulture",
    # Identity / eligibility
    "sc", "st", "obc", "ews", "bpl", "dalit", "adivasi", "tribal",
    "handicapped", "disabled", "disability", "widow", "orphan",
    "minority", "caste", "category",
    # Documents
    "aadhaar", "aadhar", "pan card", "income certificate", "caste certificate",
    "domicile", "nativity", "ration card", "voter id", "passport",
    "birth certificate", "marriage certificate", "patta", "chitta",
    # Government portals & programs
    "pmay", "pmjay", "ayushman", "nrega", "mgnrega", "jan dhan",
    "ujjwala", "mudra", "standup india", "startup india", "myscheme",
    "digilocker", "umang", "e-shram", "samman nidhi",
    # Key topics
    "eligibility", "apply", "application", "registration", "portal",
    "helpline", "how to get", "how to apply", "documents needed",
    "documents required", "government", "central government", "state government",
    "ministry", "department", "district collector", "block office",
    "panchayat", "gram sabha", "municipality", "corporation",
    # Health
    "hospital", "health", "medicine", "treatment", "maternity", "anganwadi",
    "immunization", "vaccine", "nutrition", "ration", "mid-day meal",
    # Education
    "school", "college", "education", "student", "tuition fee", "hostel",
    "merit", "meritorious", "post-matric", "pre-matric",
    # Employment
    "employment", "job", "skill", "training", "apprenticeship",
    "self-employment", "entrepreneurship", "startup", "msme",
    # Housing
    "housing", "house", "home", "shelter", "awas", "pucca", "kutcha",
    # Social security
    "swachh bharat", "toilet", "sanitation", "drinking water", "electricity",
    "solar", "gas", "lpg", "cylinder",
    # Jan-Seva specific
    "jan seva", "jan-seva", "government scheme",
    # Question words that typically precede scheme queries
    "how much", "when will", "where to", "what is the", "can i get",
    "am i eligible", "who can apply", "what documents",
}

# Partial phrase patterns that indicate on-topic (regex)
ON_TOPIC_PATTERNS = [
    r"\b(pm|pradhan mantri)\b",
    r"\b(chief minister|cm)\s*(scheme|yojana|quota)\b",
    r"\b(state|central)\s+government\b",
    r"\b(free\s+)?(ration|electricity|water|laptop|phone)\b",
    r"\b(old age|senior citizen|widow|divyang)\b",
    r"\b(apply\s+)?(online|offline)\b.*\b(scheme|benefit)\b",
    r"\b(income|age)\s+limit\b",
    r"\b(how\s+to\s+apply)\b",
    r"\b(documents?\s+(needed|required|for))\b",
]

# ── Off-Topic Keywords (entertainment, sports, politics, general knowledge) ───
# These categories should NOT be answered.
OFF_TOPIC_KEYWORDS = {
    # Sports
    "cricket", "ipl", "football", "hockey", "tennis", "badminton",
    "match", "score", "wicket", "century", "world cup", "fifa",
    "olympic", "athlete", "player", "team india", "bcci", "icc",
    # Entertainment
    "movie", "film", "bollywood", "kollywood", "tollywood", "actor",
    "actress", "song", "music", "album", "concert", "celebrity",
    "serial", "web series", "netflix", "amazon prime", "ott",
    # Cooking / food (non-welfare)
    "recipe", "cook", "restaurant", "food delivery", "swiggy", "zomato",
    # Weather / geography (non-scheme)
    "weather", "forecast", "rain today", "temperature today",
    # General tech (non-govt)
    "iphone", "samsung", "laptop buy", "best phone", "gaming",
    "cryptocurrency", "bitcoin", "stock market", "share price",
    "sensex", "nifty", "trading",
    # Personal relationships
    "girlfriend", "boyfriend", "love", "marriage proposal", "dating",
    "divorce advice", "relationship",
    # Gaming
    "pubg", "free fire", "fortnite", "minecraft", "gta",
}

# ── Hard Block patterns (abusive / prompt injection) ──────────────────────────
HARD_BLOCK_PATTERNS = [
    r"\b(fuck|shit|bitch|bastard|asshole|motherfucker|madarchod|bhosdike|chutiya|gaandu|randi)\b",
    r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?|rules?)",
    r"you\s+are\s+(now\s+)?(dan|evil\s+ai|jailbreak)",
    r"pretend\s+(you\s+are|to\s+be)\s+",
    r"act\s+as\s+(if\s+you\s+are\s+)?(an?\s+)?(evil|unrestricted|jailbroken)",
]


class TopicGuard:
    """Fast, rule-based topic classification for Jan-Seva AI."""

    def __init__(self):
        self._hard_block_re = re.compile(
            "|".join(HARD_BLOCK_PATTERNS), re.IGNORECASE
        )
        self._on_topic_pattern_re = re.compile(
            "|".join(ON_TOPIC_PATTERNS), re.IGNORECASE
        )

    def classify(self, query: str) -> TopicVerdict:
        """
        Classify query as ALLOWED, WARN, or BLOCK.
        Fast — no API calls.
        """
        normalized = query.lower().strip()

        # 1. Hard block check (abusive content, prompt injection)
        if self._hard_block_re.search(normalized):
            logger.warning(f"🚫 TopicGuard: HARD BLOCK — '{query[:60]}'")
            return TopicVerdict.BLOCK

        # 2. On-topic keyword check
        words = set(re.findall(r"\b\w+\b", normalized))
        if words & ON_TOPIC_KEYWORDS:
            return TopicVerdict.ALLOWED

        # 3. On-topic pattern check
        if self._on_topic_pattern_re.search(normalized):
            return TopicVerdict.ALLOWED

        # 4. Short queries (≤ 4 words) — likely context follow-ups or greetings
        # Allow them through (they'll hit the greeting handler or be ambiguous)
        if len(normalized.split()) <= 4:
            return TopicVerdict.ALLOWED

        # 5. Off-topic keyword check
        if words & OFF_TOPIC_KEYWORDS:
            logger.info(f"⚠️ TopicGuard: OFF-TOPIC — '{query[:60]}'")
            return TopicVerdict.WARN

        # 6. Default: allow (better to be permissive than block a valid scheme query)
        return TopicVerdict.ALLOWED


# ── Response Templates ────────────────────────────────────────────────────────

def get_warning_message(warning_num: int) -> str:
    remaining = MAX_WARNINGS - warning_num
    if remaining > 0:
        return (
            f"⚠️ **Warning {warning_num}/{MAX_WARNINGS}:** I'm Jan-Seva AI, specialized "
            f"exclusively in **Indian government schemes and citizen welfare programs**.\n\n"
            f"I can help you with:\n"
            f"- 🌾 Agricultural subsidies & PM-KISAN\n"
            f"- 🎓 Scholarships & education schemes\n"
            f"- 🏠 Housing schemes (PMAY, etc.)\n"
            f"- 💉 Health insurance (Ayushman Bharat)\n"
            f"- 💼 Employment & skill development\n\n"
            f"You have **{remaining} warning(s)** remaining before a temporary block. "
            f"Please ask about government schemes! 🙏"
        )
    return get_block_message(3600)


def get_block_message(seconds_remaining: float) -> str:
    minutes = int(seconds_remaining // 60)
    return (
        f"🚫 **Access Temporarily Blocked**\n\n"
        f"You have been blocked for **{minutes} minute(s)** due to repeated off-topic messages.\n\n"
        f"Jan-Seva AI is a specialized assistant for **Indian government schemes and citizen welfare** only.\n\n"
        f"Please try again after {minutes} minutes to ask about eligible government benefits. 🙏"
    )


def get_hard_block_message() -> str:
    return (
        "🚫 **This message cannot be processed.**\n\n"
        "Jan-Seva AI maintains strict content standards to serve all citizens respectfully.\n\n"
        "Please ask about Indian government schemes, subsidies, or welfare programs. 🙏"
    )


MAX_WARNINGS = 3

# Singleton
_guard: TopicGuard | None = None


def get_topic_guard() -> TopicGuard:
    global _guard
    if _guard is None:
        _guard = TopicGuard()
    return _guard
