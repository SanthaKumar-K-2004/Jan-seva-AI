"""
Jan-Seva AI — LLM Client (API-Only) v3.0
Dual Groq key support with multi-model fallback chain.
Deep research system prompt — state-aware, sector-separated, follow-up question aware.
"""

from groq import AsyncGroq
from app.config import get_settings
from app.utils.logger import logger
from app.core.openai_client import get_openai_client


# Ordered list of models to try (best → fastest)
FALLBACK_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "gemma2-9b-it",
    "llama3-8b-8192",
    "mixtral-8x7b-32768",
]

# Language config
LANGUAGE_CONFIG = {
    "en": {"greeting": "Hello", "name": "English"},
    "hi": {"greeting": "नमस्ते", "name": "Hindi"},
    "ta": {"greeting": "வணக்கம்", "name": "Tamil"},
    "te": {"greeting": "నమస్కారం", "name": "Telugu"},
    "kn": {"greeting": "ನಮಸ್ಕಾರ", "name": "Kannada"},
    "ml": {"greeting": "നമസ്കാരം", "name": "Malayalam"},
    "bn": {"greeting": "নমস্কার", "name": "Bengali"},
    "mr": {"greeting": "नमस्कार", "name": "Marathi"},
    "gu": {"greeting": "નમસ્તે", "name": "Gujarati"},
    "pa": {"greeting": "ਸਤ ਸ੍ਰੀ ਅਕਾਲ", "name": "Punjabi"},
    "or": {"greeting": "ନମସ୍କାର", "name": "Odia"},
    "as": {"greeting": "নমস্কাৰ", "name": "Assamese"},
    "ur": {"greeting": "السلام علیکم", "name": "Urdu"},
}

# State-specific portal & agency database
STATE_PORTALS = {
    "TN": {
        "portals": [
            "tnschemes.tn.gov.in (Tamil Nadu Schemes Portal)",
            "tahdco.tn.gov.in (SC/ST Housing & Development)",
            "tnau.ac.in (Agricultural University Schemes)",
            "sipcot.com (Industrial Land – SIPCOT)",
            "tnsocialwelfare.tn.gov.in (Social Welfare Dept)",
        ],
        "helpline": "044-2567-0170 (TN Helpline)",
        "agencies": ["TAHDCO", "TNAU", "SIPCOT", "District Collector Office"],
    },
    "MH": {
        "portals": ["mahadbte.com", "mahadbt.maharashtra.gov.in"],
        "helpline": "1800-120-8040",
        "agencies": ["MHADA", "MAVIM", "MSFC"],
    },
    "AP": {
        "portals": ["ap.gov.in", "spap.ap.gov.in"],
        "helpline": "1902",
        "agencies": ["APSCBC", "APSFC"],
    },
    "TS": {
        "portals": ["ts.gov.in", "tsiic.telangana.gov.in"],
        "helpline": "1800-425-0425",
        "agencies": ["TSIIC", "TSWAL"],
    },
    "KA": {
        "portals": ["karnataka.gov.in", "sevasindhu.karnataka.gov.in"],
        "helpline": "080-4455-4455",
        "agencies": ["KIADB", "KAWAD"],
    },
    "KL": {
        "portals": ["kerala.gov.in", "schemes.kerala.gov.in"],
        "helpline": "0471-2727-800",
        "agencies": ["KSIDC", "NORKA"],
    },
    "UP": {
        "portals": ["up.gov.in", "sspy-up.gov.in"],
        "helpline": "1800-180-5131",
        "agencies": ["UPSIDC", "UPSRLM"],
    },
    "WB": {
        "portals": ["wb.gov.in", "wbifms.wb.gov.in"],
        "helpline": "1800-103-0009",
        "agencies": ["WBHIDCO", "WBSeDC"],
    },
    # Default / central
    "_central": {
        "portals": [
            "myscheme.gov.in (National Scheme Portal)",
            "india.gov.in (National Portal of India)",
            "pmkisan.gov.in (PM-KISAN)",
            "pmjay.gov.in (Ayushman Bharat)",
            "pmayg.nic.in (PM Awas Yojana – Rural)",
        ],
        "helpline": "1800-11-0031 (Central Government Helpline)",
        "agencies": ["District Collector", "CSC (Common Service Centre)", "Block Development Office"],
    },
}


def get_state_context(state: dict | None) -> str:
    """Build a state-specific context hint for the system prompt."""
    if not state:
        code = "_central"
    else:
        code = state.get("code", "_central")

    info = STATE_PORTALS.get(code, STATE_PORTALS["_central"])
    central = STATE_PORTALS["_central"]

    lines = []
    if state:
        lines.append(f"\n🗺️ USER'S STATE: {state['name']} ({code})")
        lines.append("Official Portals to cite for this state:")
        for p in info["portals"]:
            lines.append(f"  • {p}")
        lines.append(f"State Helpline: {info['helpline']}")
        lines.append(f"Key Agencies: {', '.join(info['agencies'])}")

    lines.append("\nAlways ALSO include Central Government schemes:")
    for p in central["portals"]:
        lines.append(f"  • {p}")
    lines.append(f"Central Helpline: {central['helpline']}")

    return "\n".join(lines)


def get_system_prompt(
    language: str = "en",
    state: dict | None = None,
    sector: str | None = None,
    user_profile: dict | None = None,
) -> str:
    lang_cfg = LANGUAGE_CONFIG.get(language, LANGUAGE_CONFIG["en"])
    greeting = lang_cfg["greeting"]
    lang_name = lang_cfg["name"]
    state_ctx = get_state_context(state)
    state_name = state["name"] if state else "India"
    sector_display = sector.replace("_", " ").title() if sector else "All Sectors"

    profile_summary = ""
    if user_profile:
        parts = []
        if user_profile.get("age"):
            parts.append(f"Age: {user_profile['age']}")
        if user_profile.get("caste_category"):
            parts.append(f"Caste: {user_profile['caste_category']}")
        if user_profile.get("occupation"):
            parts.append(f"Occupation: {user_profile['occupation']}")
        if user_profile.get("income_per_year"):
            income_lakh = user_profile["income_per_year"] / 100000
            parts.append(f"Income: ₹{income_lakh:.1f} lakh/year")
        if user_profile.get("gender"):
            parts.append(f"Gender: {user_profile['gender']}")
        if parts:
            profile_summary = f"\n👤 KNOWN USER PROFILE: {' | '.join(parts)}"

    # ── Sector-level real-scheme knowledge hints (prevents hallucination) ──────
    SECTOR_KNOWLEDGE = {
        "agricultural": """
🌾 VERIFIED SCHEMES — Use these as base; confirm exact amounts from research data:
  CENTRAL GOVERNMENT:
  • PM-KISAN: ₹6,000/year (3×₹2,000 installments) to ALL landholding farmer families
    Docs: Aadhaar (eKYC mandatory), land records/patta, IFSC-linked bank account | Portal: pmkisan.gov.in
  • PM Krishi Sinchai Yojana (PMKSY): Drip/sprinkler subsidy — 55% for small/marginal, 45% others
    Docs: Land records, Aadhaar, water availability proof | Portal: pmksy.gov.in
  • Soil Health Card Scheme: FREE soil testing + fertilizer recommendations every 2 years
    Docs: Aadhaar, land survey number | Portal: soilhealth.dac.gov.in
  • NABARD DEDS (Dairy Entrepreneurship Development Scheme): 25% subsidy (33% for SC/ST) capped at ₹3.3 lakh
    Docs: Project DPR, land lease/ownership, bank loan sanction | Via NABARD district office
  • SFAC (Small Farmers Agribusiness Consortium): Grant up to ₹25 lakh for agroprocessing projects
    Docs: Business plan, land records, CA-certified accounts | Portal: sfacindia.com
  STATE LEVEL (only include if user's state is TN/AP/KA/MH/UP — confirm from context):
  • TAHDCO Land Subsidy (Tamil Nadu SC/ST ONLY): ₹1,00,000 for 1 acre dry land purchase
    Docs: Community cert (SC/ST), income cert <₹1L/yr, survey extract, bank passbook | tahdco.tn.gov.in
  • TNAU Farm Machinery (Tamil Nadu): 50% subsidy up to ₹1,50,000 on agri equipment
    Docs: Pattadar passbook, Aadhaar, bank details | tnau.ac.in/schemes
  • Karnataka SC/ST Free Land (Sthalavara Yojane): 1 acre free to landless SC/ST laborers
    Docs: SC/ST certificate, BPL card, income cert, residence proof | Karnataka Revenue Dept
  ⚠️ WARNING: "PM Kisan Tractor Scheme" is NOT a central government scheme.
    Tractor subsidies are STATE-LEVEL only. Each state has its own portal (e.g., upagriculture.com for UP).
    Do NOT use "kisanportal.org" — this is an UNOFFICIAL, unreliable site. NEVER cite it.""",
        "housing": """
🏠 VERIFIED SCHEMES:
  • PMAY-G (Rural): ₹1,20,000 (plains) / ₹1,30,000 (NE/hilly areas) — pmayg.nic.in | Docs: Aadhaar, SECC data, bank account
  • PMAY-U (Urban EWS/LIG Credit-Linked): Interest subsidy ₹2.67 lakh max — pmaymis.gov.in
  • TAHDCO Housing (TN SC/ST): Up to ₹5,00,000 for house construction — tahdco.tn.gov.in""",
        "education": """
📚 VERIFIED SCHEMES:
  • NSP (National Scholarship Portal): Multiple central scholarships — scholarships.gov.in
  • Post-Matric Scholarship for SC: Tuition fee + maintenance allowance (state-specific amounts)
  • PM Yasasvi Scholarship (OBC/EWS): ₹75,000–₹1,25,000/year — yet.nta.ac.in"""
    }
    sector_knowledge = SECTOR_KNOWLEDGE.get(sector, "") if sector else ""

    # ── Unknown-state guard: prevents random multi-state guessing ─────────────
    state_unknown = not state
    state_question_rule = ""
    if state_unknown:
        state_question_rule = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚨 STATE NOT DETECTED — MANDATORY BEHAVIOUR
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The user's state is NOT known yet. You MUST follow these rules STRICTLY:
1. Cover ONLY Central Government schemes (those that work in every state) in your response.
2. Do NOT list schemes from multiple different states (e.g., UP + Bihar + TN) — the user only lives in ONE state and this is misleading.
3. AFTER giving the central schemes summary, ask EXACTLY this:
   "📍 To show you the BEST state-specific schemes available in your state, could you please tell me which state you're from? (e.g., Tamil Nadu, Maharashtra, Uttar Pradesh, etc.)"
4. Keep the central-schemes section concise — 3-4 schemes maximum until state is confirmed."""

    return f"""You are **Jan-Seva AI** — India's Most Advanced Government Scheme Research Analyst.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LANGUAGE: {lang_name} | REGION: {state_name} | SECTOR: {sector_display}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Respond ENTIRELY in **{lang_name}**.
- Tone: Expert, Empathetic, Precise, Action-oriented.
- You are a Senior Government Scheme Research Analyst — the most knowledgeable government advisor in India.
{profile_summary}
{state_ctx}

{sector_knowledge}

{state_question_rule}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RESPONSE STRUCTURE (follow in this order)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**1. 🌟 Executive Summary** (2-3 lines)
   Precise answer: how many schemes exist, total benefit range.

**2. 🇮🇳 Central Government Schemes** (ALWAYS first — these work in all states)
   For EACH scheme (3-5 schemes max):
   - **🎯 Scheme:** Full official name + implementing ministry
   - **💰 Benefits:** EXACT ₹ amount or exact % — e.g., "₹6,000/year" NOT "some annual support"
   - **📋 Eligibility:** Income ceiling, land size, category (SC/ST/OBC/General), age limits
   - **📄 Documents (SCHEME-SPECIFIC — find in research data):**
     • [What THIS scheme uniquely requires — NOT a copy-paste list]
   - **🔗 Official Portal:** [Domain ending in .gov.in or .nic.in ONLY]
   - **☎️ Helpline:** [Verified number]

**3. 🏛️ [{state_name}] State Government Schemes** (ONLY if state is confirmed known)
   — If state is unknown, SKIP this section and ask for state at the end —
   (Same per-scheme structure as above)

**4. 📋 Step-by-Step Application Guide** (for the most accessible scheme)
   1. Go to [exact URL]
   2. Click [exact menu item]
   3. Fill [form/section name] — key fields: land area, Aadhaar No., bank IFSC
   4. Upload: [list exact documents with file format requirements]
   5. Submit → Note your Reference/Application Number
   6. Track status: [URL] → select [menu path]

**5. ⚠️ Critical Checks Before Applying**
   - [Specific document/eligibility trap unique to this scheme]
   - [Live portal status check: is it open for applications?]

**6. 💡 Expert Insider Tips** (only 1-2, genuinely useful)
   - [Something a first-time applicant would NOT know]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRITICAL RULES — NEVER BREAK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ EXACT ₹ figures always — never "financial assistance" or "some subsidy"
✅ SCHEME-SPECIFIC docs — pull from research data, do NOT use same list for every scheme
✅ .gov.in / .nic.in URLs ONLY — never unofficial sites like kisanportal.org, yojanainfo.com
✅ CENTRAL schemes FIRST, then state schemes
✅ If STATE unknown → list only central schemes (3-4 max), then ASK: "Which state are you from?"
✅ If unsure of an amount → say "verify at [official portal]" — never fabricate
✅ If profile info missing → ask 2-3 targeted questions AFTER the central scheme summary
❌ NEVER list random state schemes (UP + Bihar + TN) when you don't know the user's state
❌ NEVER use unofficial portals or third-party websites
❌ NEVER copy-paste identical documents across multiple schemes
❌ NEVER invent scheme names not found in the research data
❌ NEVER say "PM Kisan Tractor Scheme" is a CENTRAL scheme — it is STATE-LEVEL
"""


class LLMClient:
    """
    Groq LLM wrapper with dual API key support and multi-model fallback.
    State-aware, sector-aware, profile-aware deep research prompt.
    """

    def __init__(self):
        settings = get_settings()
        self.api_keys = settings.all_groq_keys
        self.max_tokens = settings.llm_max_tokens
        self.default_temperature = settings.llm_temperature

        if not self.api_keys:
            logger.error("❌ No GROQ_API_KEY found! Set at least one in .env")
            raise ValueError("At least one GROQ_API_KEY is required")

        self.clients = [AsyncGroq(api_key=key) for key in self.api_keys]

        # Add OpenAI client
        self.openai = get_openai_client()

        logger.info(
            f"✅ LLM Client v3: {len(self.clients)} Groq keys | "
            f"OpenAI: {self.openai.model if self.openai.client else 'OFF'} | "
            f"Models: {' → '.join(FALLBACK_MODELS)} | MaxTokens: {self.max_tokens}"
        )

    async def generate(
        self,
        user_query: str,
        context: str,
        chat_history: list = None,
        language: str = "en",
        is_greeting: bool = False,
        state: dict | None = None,
        sector: str | None = None,
        user_profile: dict | None = None,
    ) -> str:
        """
        Generates a deep, structured response.
        Tries: OpenAI → Key1/Model1 → Key1/Model2 → ... → Key2/ModelN
        """
        if chat_history is None:
            chat_history = []

        system_prompt = get_system_prompt(language, state, sector, user_profile)
        messages = [{"role": "system", "content": system_prompt}]

        for msg in chat_history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if content:
                messages.append({"role": role, "content": content})

        lang_name = LANGUAGE_CONFIG.get(language, LANGUAGE_CONFIG["en"])["name"]

        if is_greeting:
            user_prompt = (
                f"CONTEXT:\n{context}\n\n"
                f"USER MESSAGE: {user_query}\n\n"
                f"IMPORTANT: Respond in {lang_name}. Give a warm, SHORT welcome (3-5 sentences max)."
            )
        else:
            state_hint = f"USER'S STATE: {state['name']} ({state['code']})" if state else "USER'S STATE: UNKNOWN — Cover central schemes ONLY, then ask which state they're from."
            user_prompt = (
                f"RESEARCH DATA (authoritative sources — government portals, news, Wikipedia):\n"
                f"{context}\n\n"
                f"════ USER CONTEXT ════\n"
                f"USER QUESTION: {user_query}\n"
                f"{state_hint}\n"
                f"LANGUAGE TO RESPOND IN: {lang_name}\n\n"
                f"════ CRITICAL INSTRUCTIONS ════\n"
                f"1. Respond ENTIRELY in {lang_name}.\n"
                f"2. Use EXACT ₹ amounts — e.g., '₹6,000/year' NOT 'annual financial support'.\n"
                f"3. CENTRAL GOVERNMENT schemes FIRST (always work in all states).\n"
                f"4. If state is known, add a SEPARATE STATE SCHEMES section after central.\n"
                f"5. If state is UNKNOWN, do NOT list random state schemes (no UP + Bihar + TN guessing). "
                f"Cover central only, then ask: '📍 Which state are you from?'\n"
                f"6. Documents must be SCHEME-SPECIFIC (from research data) — not generic Aadhaar+land cert for every scheme.\n"
                f"7. Use ONLY .gov.in or .nic.in portal URLs. NEVER use unofficial sites.\n"
                f"8. Include Step-by-Step application guide for the most accessible scheme.\n"
                f"9. If income/caste/age is missing and scheme eligibility depends on it, ask 2-3 targeted questions.\n"
                f"10. Format: emoji headings, **bold ₹ amounts**, numbered steps.\n"
                f"11. Cite sources clearly: include official URL, source name, and publication date if available."
            )
        messages.append({"role": "user", "content": user_prompt})

        # Deep research needs more tokens and lower temperature
        max_tokens = min(256, self.max_tokens) if is_greeting else self.max_tokens
        temperature = 0.5 if is_greeting else self.default_temperature

        last_error = None

        # Try OpenAI First (Highest quality)
        if self.openai.async_client:
            try:
                logger.info(f"🦾 OpenAI → {self.openai.model}{' (greeting)' if is_greeting else ''}")
                answer = await self.openai.generate(system_prompt, user_prompt, temperature=temperature)
                if answer:
                    logger.info(f"✅ Response from OpenAI/{self.openai.model} ({len(answer)} chars)")
                    return answer
            except Exception as e:
                last_error = e
                logger.warning(f"⚠️ OpenAI failed: {e}")

        # Try each Groq key × each model
        for key_idx, client in enumerate(self.clients):
            for model in FALLBACK_MODELS:
                try:
                    logger.info(f"🤖 Key {key_idx + 1} → {model}{' (greeting)' if is_greeting else ''}")
                    response = await client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    answer = response.choices[0].message.content.strip()
                    if answer:
                        logger.info(f"✅ Response from Key{key_idx + 1}/{model} ({len(answer)} chars)")
                        return answer
                    continue
                except Exception as e:
                    last_error = e
                    logger.warning(f"⚠️ Key{key_idx + 1}/{model} failed: {type(e).__name__}: {e}")
                    continue

        error_msg = (
            f"All LLM attempts failed ({len(self.clients)} keys × {len(FALLBACK_MODELS)} models). "
            f"Last: {last_error}"
        )
        logger.error(f"❌ {error_msg}")
        raise RuntimeError(error_msg)


# --- Singleton ---
_llm_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
