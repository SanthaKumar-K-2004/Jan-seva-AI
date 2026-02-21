"""
Jan-Seva AI — Query Classifier
Classifies user intent, extracts state/sector/user-type context,
and selects optimal API providers to query.
Rule-based for zero latency. No extra API calls needed.
"""

import re
from app.utils.logger import logger


class QueryIntent:
    """Enumeration of query intents."""
    GREETING = "greeting"
    SCHEME_DISCOVERY = "scheme_discovery"
    ELIGIBILITY_CHECK = "eligibility_check"
    APPLICATION_HELP = "application_help"
    LATEST_NEWS = "latest_news"
    GENERAL_KNOWLEDGE = "general_knowledge"
    COMPARISON = "comparison"
    DOCUMENTS = "documents"


# Greeting patterns (multi-language)
GREETING_PATTERNS = {
    "hi", "hello", "hey", "hii", "hiii", "helo", "hola", "yo", "sup", "howdy",
    "greetings", "good morning", "good afternoon", "good evening", "good night",
    "gm", "gn", "morning", "evening", "what's up", "whats up", "wassup",
    "how are you", "how r u", "how are u", "how do you do", "nice to meet you",
    "namaste", "namaskar", "namaskaaram", "pranam", "pranaam",
    "नमस्ते", "नमस्कार", "प्रणाम", "राम राम", "जय हिंद",
    "vanakkam", "வணக்கம்", "namaskaram", "నమస్కారం",
    "namaskara", "ನಮಸ್ಕಾರ", "നമസ്കാരം", "nomoshkar", "নমস্কার",
    "kem cho", "કેમ છો", "sat sri akal", "ਸਤ ਸ੍ਰੀ ਅਕਾਲ",
    "ନମସ୍କାର", "assalam alaikum", "salam", "السلام علیکم",
}

# Intent keyword maps
ELIGIBILITY_KEYWORDS = [
    "eligible", "eligibility", "qualify", "qualification", "criteria",
    "am i eligible", "can i apply", "can i get", "who can apply",
    "income limit", "age limit", "patra", "yogya",
]

APPLICATION_KEYWORDS = [
    "how to apply", "application", "apply online", "registration",
    "form", "register", "submit", "portal", "website", "link",
    "kaise apply", "avedan", "aavedan",
]

NEWS_KEYWORDS = [
    "new", "latest", "recent", "update", "2024", "2025", "2026",
    "announced", "launched", "modified", "changed", "current",
    "nayi", "naya", "taaza",
]

DOCUMENT_KEYWORDS = [
    "documents", "document", "papers", "required", "proof",
    "aadhaar", "aadhar", "pan card", "income certificate",
    "caste certificate", "domicile", "dastavez",
]

COMPARISON_KEYWORDS = [
    "compare", "comparison", "difference", "vs", "versus",
    "better", "best", "which one", "which scheme",
]


# ── State Detection Map ──────────────────────────────────────────────────────
STATE_KEYWORDS: dict[str, dict] = {
    # South
    "tamil nadu": {"code": "TN", "name": "Tamil Nadu"},
    "tamilnadu": {"code": "TN", "name": "Tamil Nadu"},
    "tn": {"code": "TN", "name": "Tamil Nadu"},
    "kerala": {"code": "KL", "name": "Kerala"},
    "karnataka": {"code": "KA", "name": "Karnataka"},
    "andhra": {"code": "AP", "name": "Andhra Pradesh"},
    "andhra pradesh": {"code": "AP", "name": "Andhra Pradesh"},
    "telangana": {"code": "TS", "name": "Telangana"},
    # West
    "maharashtra": {"code": "MH", "name": "Maharashtra"},
    "goa": {"code": "GA", "name": "Goa"},
    "gujarat": {"code": "GJ", "name": "Gujarat"},
    "rajasthan": {"code": "RJ", "name": "Rajasthan"},
    # North
    "delhi": {"code": "DL", "name": "Delhi"},
    "uttar pradesh": {"code": "UP", "name": "Uttar Pradesh"},
    "up": {"code": "UP", "name": "Uttar Pradesh"},
    "haryana": {"code": "HR", "name": "Haryana"},
    "punjab": {"code": "PB", "name": "Punjab"},
    "himachal": {"code": "HP", "name": "Himachal Pradesh"},
    "himachal pradesh": {"code": "HP", "name": "Himachal Pradesh"},
    "uttarakhand": {"code": "UK", "name": "Uttarakhand"},
    "jammu": {"code": "JK", "name": "Jammu & Kashmir"},
    "kashmir": {"code": "JK", "name": "Jammu & Kashmir"},
    # East
    "west bengal": {"code": "WB", "name": "West Bengal"},
    "bengal": {"code": "WB", "name": "West Bengal"},
    "bihar": {"code": "BR", "name": "Bihar"},
    "jharkhand": {"code": "JH", "name": "Jharkhand"},
    "odisha": {"code": "OD", "name": "Odisha"},
    "orissa": {"code": "OD", "name": "Odisha"},
    # North East
    "assam": {"code": "AS", "name": "Assam"},
    "meghalaya": {"code": "ML", "name": "Meghalaya"},
    "manipur": {"code": "MN", "name": "Manipur"},
    "nagaland": {"code": "NL", "name": "Nagaland"},
    "sikkim": {"code": "SK", "name": "Sikkim"},
    "tripura": {"code": "TR", "name": "Tripura"},
    "mizoram": {"code": "MZ", "name": "Mizoram"},
    "arunachal": {"code": "AR", "name": "Arunachal Pradesh"},
    # Central
    "madhya pradesh": {"code": "MP", "name": "Madhya Pradesh"},
    "mp": {"code": "MP", "name": "Madhya Pradesh"},
    "chhattisgarh": {"code": "CG", "name": "Chhattisgarh"},
    "chattisgarh": {"code": "CG", "name": "Chhattisgarh"},
}

# ── Sector Keywords ──────────────────────────────────────────────────────────
SECTOR_KEYWORDS: dict[str, list[str]] = {
    "agricultural": [
        "land", "farm", "farmer", "agriculture", "kisan", "krishi",
        "crop", "soil", "irrigation", "tahdco", "tnau", "patta", "subsidy land",
        "horticulture", "aquaculture", "fishery",
    ],
    "industrial": [
        "industry", "industrial", "msme", "manufacturing", "sipcot",
        "factory", "enterprise", "business", "startup",
    ],
    "housing": [
        "house", "home", "housing", "pmay", "awas", "shelter",
        "construction", "flat", "apartment",
    ],
    "education": [
        "scholarship", "school", "college", "student", "education",
        "fee", "tuition", "stipend", "merit", "post-matric",
    ],
    "health": [
        "health", "hospital", "medicine", "ayushman", "pmjay",
        "maternity", "nutrition", "vaccine", "treatment",
    ],
    "employment": [
        "job", "employment", "skill", "training", "nrega", "mgnrega",
        "mudra", "self-employment", "apprenticeship",
    ],
    "social_security": [
        "pension", "widow", "old age", "disabled", "handicap",
        "ration", "bpl", "jan dhan", "ujjwala",
    ],
}

# ── User Type Keywords ───────────────────────────────────────────────────────
USER_TYPE_KEYWORDS: dict[str, list[str]] = {
    "sc_st": ["sc", "st", "dalit", "adivasi", "tribal", "scheduled caste", "scheduled tribe"],
    "obc": ["obc", "other backward"],
    "ews": ["ews", "economically weaker"],
    "bpl": ["bpl", "below poverty", "ration card"],
    "farmer": ["farmer", "kisan", "agriculture", "farm"],
    "student": ["student", "scholarship", "school", "college", "education"],
    "woman": ["woman", "women", "mahila", "female", "girl"],
    "senior_citizen": ["senior citizen", "old age", "elderly", "pensioner"],
    "disabled": ["disabled", "handicap", "divyang", "differently abled"],
    "minority": ["minority", "muslim", "christian", "sikh", "buddhist"],
}


# Provider routing per intent
INTENT_PROVIDERS = {
    QueryIntent.GREETING: [],  # No search needed
    QueryIntent.SCHEME_DISCOVERY: ["tavily", "ddg", "nvidia", "openai", "gemini", "wikipedia"],
    QueryIntent.ELIGIBILITY_CHECK: ["tavily", "nvidia", "openai", "gemini", "ddg"],
    QueryIntent.APPLICATION_HELP: ["tavily", "ddg", "openai", "gemini"],
    QueryIntent.LATEST_NEWS: ["tavily", "news", "ddg", "openai"],
    QueryIntent.GENERAL_KNOWLEDGE: ["tavily", "wikipedia", "ddg", "openai", "gemini"],
    QueryIntent.COMPARISON: ["tavily", "nvidia", "openai", "gemini", "wikipedia"],
    QueryIntent.DOCUMENTS: ["tavily", "ddg", "openai", "gemini"],
}


class QueryClassifier:
    """
    Classifies user queries into intents and extracts rich context
    (state, sector, user type) for targeted search and personalization.
    Zero latency — no API calls needed for classification.
    """

    def classify(self, query: str) -> tuple[str, list[str]]:
        """
        Classify query intent and return (intent, provider_names).
        Returns: (intent_type, list of provider keys to query)
        """
        cleaned = query.strip().lower()
        cleaned_no_punct = re.sub(r'[!?.,;:\'"]+', '', cleaned).strip()

        # Greeting detection (fast path)
        if self._is_greeting(cleaned_no_punct):
            logger.info(f"👋 Classified as GREETING: '{query[:50]}'")
            return QueryIntent.GREETING, INTENT_PROVIDERS[QueryIntent.GREETING]

        # Score each intent
        scores = {
            QueryIntent.ELIGIBILITY_CHECK: self._score_keywords(cleaned, ELIGIBILITY_KEYWORDS),
            QueryIntent.APPLICATION_HELP: self._score_keywords(cleaned, APPLICATION_KEYWORDS),
            QueryIntent.LATEST_NEWS: self._score_keywords(cleaned, NEWS_KEYWORDS),
            QueryIntent.DOCUMENTS: self._score_keywords(cleaned, DOCUMENT_KEYWORDS),
            QueryIntent.COMPARISON: self._score_keywords(cleaned, COMPARISON_KEYWORDS),
        }

        # Get highest scoring intent
        best_intent = max(scores, key=scores.get)
        best_score = scores[best_intent]

        # If no strong match, default based on query length
        if best_score == 0:
            if len(cleaned.split()) <= 3:
                best_intent = QueryIntent.GENERAL_KNOWLEDGE
            else:
                best_intent = QueryIntent.SCHEME_DISCOVERY

        providers = INTENT_PROVIDERS[best_intent]
        logger.info(f"🔀 Classified '{query[:50]}...' → {best_intent} → [{', '.join(providers)}]")
        return best_intent, providers

    def extract_context(self, query: str) -> dict:
        """
        Extract rich context from the query:
        - state: {"code": "TN", "name": "Tamil Nadu"} or None
        - sector: "agricultural" | "housing" | "education" | ... | None
        - user_types: ["farmer", "sc_st", ...] or []
        - year_hint: "2024" | "2025" | "2026" | None
        """
        normalized = query.lower()

        # State extraction
        state = None
        for keyword, state_info in STATE_KEYWORDS.items():
            if keyword in normalized:
                state = state_info
                break

        # Sector extraction (allow multiple, return highest match)
        sector_scores = {}
        for sector, keywords in SECTOR_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in normalized)
            if score > 0:
                sector_scores[sector] = score
        sector = max(sector_scores, key=sector_scores.get) if sector_scores else None

        # User type extraction
        user_types = []
        for utype, keywords in USER_TYPE_KEYWORDS.items():
            if any(kw in normalized for kw in keywords):
                user_types.append(utype)

        # Year hint
        year_hint = None
        for year in ["2026", "2025", "2024", "2023"]:
            if year in normalized:
                year_hint = year
                break

        ctx = {
            "state": state,
            "sector": sector,
            "user_types": user_types,
            "year_hint": year_hint,
        }
        logger.debug(f"🔍 Context extracted: {ctx}")
        return ctx

    def _is_greeting(self, text: str) -> bool:
        if text in GREETING_PATTERNS:
            return True
        words = text.split()
        if len(words) <= 4 and words and words[0] in GREETING_PATTERNS:
            return True
        for greeting in GREETING_PATTERNS:
            if ' ' in greeting and text.startswith(greeting):
                return True
        return False

    def _score_keywords(self, text: str, keywords: list[str]) -> int:
        return sum(1 for kw in keywords if kw in text)


# Singleton
_classifier = None

def get_query_classifier() -> QueryClassifier:
    global _classifier
    if _classifier is None:
        _classifier = QueryClassifier()
    return _classifier
