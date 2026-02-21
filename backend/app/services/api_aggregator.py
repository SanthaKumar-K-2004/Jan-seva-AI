"""
Jan-Seva AI — API Aggregator (Main Orchestrator) v3.0
Replaces the old RAG service. Queries multiple APIs simultaneously,
scores results, and synthesizes the best answer via LLM.

New in v3.0:
  - Session-aware (loads user profile & chat history from session_store)
  - State-aware (injects resolved IP state or query-extracted state)
  - Multi-query fan-out (expands 1 query into 4 targeted sub-queries)
  - Conversational profile extraction (mines user messages for profile data)

Zero database dependencies. All data from live API calls.
"""

import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Optional
from app.config import get_settings
from app.services.query_classifier import get_query_classifier, QueryIntent
from app.services.quality_scorer import get_quality_scorer
from app.services.providers.base import SearchResult, ProviderResponse
from app.utils.logger import logger


# Provider registry — lazy loaded
_providers = {}


def _get_providers() -> dict:
    """Lazy-load all available providers."""
    global _providers
    if not _providers:
        settings = get_settings()
        from app.services.providers.tavily_provider import TavilyProvider
        from app.services.providers.ddg_provider import DuckDuckGoProvider
        from app.services.providers.wikipedia_provider import WikipediaProvider
        from app.services.providers.news_provider import NewsProvider
        from app.services.providers.nvidia_provider import NvidiaProvider
        from app.services.providers.google_provider import GoogleGeminiProvider

        _providers = {
            "tavily": TavilyProvider(),
            "ddg": DuckDuckGoProvider(),
            "wikipedia": WikipediaProvider(),
            "news": NewsProvider(),
            "nvidia": NvidiaProvider(),
            "gemini": GoogleGeminiProvider(),
        }
        if settings.enable_openai_research_provider:
            from app.services.providers.openai_provider import OpenAIProvider
            _providers["openai"] = OpenAIProvider()
    return _providers


GREETING_CONTEXT = (
    "The user has just greeted you. This is the START of a conversation. "
    "Respond with a warm, friendly, and concise welcome. Introduce yourself as Jan-Seva AI, "
    "a government scheme assistant for India. Briefly mention 2-3 things you can help with "
    "(like finding eligible schemes, application guidance, documents needed). "
    "Keep the response SHORT (3-5 sentences max). End by asking how you can help them today. "
    "Do NOT give a dictionary definition of the greeting word. "
    "Do NOT search the web or cite sources. Just be friendly and welcoming."
)


class APIAggregator:
    """
    Main orchestrator:
    1. Loads session profile & state
    2. Classifies intent + extracts query context
    3. Expands into 4 targeted sub-queries (multi-query fan-out)
    4. Fires parallel async requests to providers
    5. Scores & ranks all results
    6. Builds rich LLM context (with profile + research directive)
    7. Synthesizes deep, sector-separated answer via LLM
    8. Mines reply for new profile data
    """

    def __init__(self):
        self._llm = None
        self._cache = None
        self.settings = get_settings()

    def _get_llm(self):
        if self._llm is None:
            from app.core.llm_client import get_llm_client
            self._llm = get_llm_client()
        return self._llm

    def _get_cache(self):
        if self._cache is None:
            from app.services.research_cache import get_research_cache
            self._cache = get_research_cache()
        return self._cache

    async def query(
        self,
        user_query: str,
        user_id: str = None,
        language: str = "en",
        chat_history: list = None,
        session_id: str = None,
        resolved_state: dict = None,  # From IP detection
    ) -> dict:
        """
        Main query pipeline — fully API-driven, session-aware.
        Returns: {"answer": str, "sources": list, "images": list, "schemes": list, "language": str}
        """
        from app.services import session_store

        effective_session = session_id or user_id or "anonymous"

        classifier = get_query_classifier()
        intent, provider_keys = classifier.classify(user_query)

        # ── Fast path: Greeting ──
        if intent == QueryIntent.GREETING:
            return await self._handle_greeting(user_query, user_id, language)

        # ── Load session profile & history ──
        profile = session_store.get_profile(effective_session)
        session_history = session_store.get_chat_history(effective_session, last_n=8)
        if chat_history:  # caller-supplied history takes precedence
            session_history = chat_history[-8:]

        # ── Extract context from query ──
        ctx = classifier.extract_context(user_query)
        query_state = ctx.get("state")
        sector = ctx.get("sector")
        user_types = ctx.get("user_types", [])
        year_hint = ctx.get("year_hint") or str(datetime.now(timezone.utc).year)
        profile_fingerprint = self._build_profile_fingerprint(profile, sector, user_types)

        # ── Resolve final state (priority: query mention > IP > session profile) ──
        final_state = (
            query_state
            or resolved_state
            or ({"code": profile.get("state_code"), "name": profile.get("state")}
                if profile.get("state") else None)
        )

        # Update session with newly discovered state
        if query_state and not profile.get("state"):
            session_store.update_profile(effective_session, {
                "state_code": query_state["code"],
                "state_name": query_state["name"],
            })

        # ── Mine query for profile data ──
        self._mine_profile_from_query(user_query, effective_session)

        # ── Translation (if not English) ──
        english_query = user_query
        detected_lang = language
        if language not in ("en", "auto"):
            english_query, detected_lang = await self._translate_to_english(user_query, language)
        elif language == "auto":
            english_query, detected_lang = await self._detect_and_translate(user_query)

        # -- Persistent cache lookup --
        state_code = final_state.get("code") if final_state else None
        cache = self._get_cache()
        cached_payload = cache.get(
            query=english_query,
            language=detected_lang,
            intent=intent,
            state_code=state_code,
            profile_fingerprint=profile_fingerprint,
        )
        if cached_payload:
            logger.info(f"Cache hit for intent={intent} lang={detected_lang} state={state_code or 'NA'}")
            session_store.append_chat(effective_session, "user", user_query)
            session_store.append_chat(effective_session, "assistant", cached_payload.get("answer", ""))

            cached_payload.setdefault("answer", "")
            cached_payload.setdefault("sources", [])
            cached_payload.setdefault("images", [])
            cached_payload.setdefault("language", detected_lang)
            cached_payload.setdefault("intent", intent)
            cached_payload.setdefault("providers_queried", ["cache"])
            cached_payload.setdefault("schemes", [])
            cached_payload.setdefault("state_detected", final_state)
            cached_payload["cache_hit"] = True
            return cached_payload

        # ── Multi-query fan-out ──
        sub_queries = self._expand_queries(english_query, final_state, sector, user_types, year_hint)
        logger.info(f"🔀 Fan-out: {len(sub_queries)} sub-queries for '{english_query[:50]}'")

        # ── Parallel provider requests (all sub-queries × selected providers) ──
        providers = _get_providers()
        selected = {k: providers[k] for k in provider_keys if k in providers and providers[k].is_available()}
        logger.info(f"🚀 Querying {len(selected)} providers × {len(sub_queries)} sub-queries")

        tasks = {}
        for q_idx, sub_q in enumerate(sub_queries):
            # Primary sub-query hits all selected providers
            # Additional sub-queries only hit Tavily (fast, AI-optimised)
            if q_idx == 0:
                for key, provider in selected.items():
                    task_key = f"{key}_{q_idx}"
                    tasks[task_key] = asyncio.create_task(provider.search(sub_q))
            else:
                if "tavily" in selected:
                    task_key = f"tavily_{q_idx}"
                    tasks[task_key] = asyncio.create_task(selected["tavily"].search(sub_q))
                elif "ddg" in selected:
                    task_key = f"ddg_{q_idx}"
                    tasks[task_key] = asyncio.create_task(selected["ddg"].search(sub_q))

        # Wait with a global timeout
        responses: dict[str, ProviderResponse] = {}
        done, pending = await asyncio.wait(
            tasks.values(),
            timeout=28.0,
            return_when=asyncio.ALL_COMPLETED,
        )
        for task in pending:
            task.cancel()

        for key, task in tasks.items():
            try:
                if task.done() and not task.cancelled():
                    responses[key] = task.result()
                else:
                    logger.warning(f"⏰ Task {key} timed out")
            except Exception as e:
                logger.warning(f"⚠️ Task {key} error: {e}")

        # ── Collect & score results ──
        all_results = []
        all_images = []
        ai_answers = []

        for key, resp in responses.items():
            if resp.success:
                all_results.extend(resp.results)
                all_images.extend(resp.images)
                if resp.answer:
                    provider_label = key.split("_")[0].upper()
                    ai_answers.append(f"[{provider_label}]: {resp.answer}")

        scorer = get_quality_scorer()
        verified_results = scorer.filter_verified_results(
            all_results,
            query_intent=intent,
            min_reliability=self.settings.min_source_reliability,
            max_age_days=self.settings.max_source_age_days,
            max_news_age_days=self.settings.max_news_age_days,
        )

        if self.settings.strict_verified_mode and verified_results:
            scoring_pool = verified_results
        else:
            scoring_pool = all_results
            if self.settings.strict_verified_mode and all_results and not verified_results:
                logger.warning(
                    "Strict verification enabled but no results passed filters. "
                    "Using unfiltered results to avoid empty answer."
                )

        ranked_results = scorer.score_results(scoring_pool, english_query, top_k=12)

        # ── Build rich LLM context ──
        context = self._build_context(
            ranked_results, ai_answers, all_images,
            final_state, sector, user_types, profile,
            intent=intent, strict_verified=self.settings.strict_verified_mode,
        )

        # ── LLM synthesis ──
        llm = self._get_llm()
        answer = await llm.generate(
            user_query=english_query,
            context=context if context else (
                "No external data available. Answer based on your general knowledge "
                "about Indian government schemes."
            ),
            chat_history=session_history,
            language=detected_lang,
            state=final_state,
            sector=sector,
            user_profile=profile,
        )

        # ── Translate back if needed ──
        if detected_lang != "en":
            answer = await self._translate_response(answer, detected_lang)

        # ── Save to session history ──
        session_store.append_chat(effective_session, "user", user_query)
        session_store.append_chat(effective_session, "assistant", answer)

        # ── Build source citations ──
        sources = []
        for r in ranked_results[:6]:
            reliability = scorer.domain_reliability(r.domain)
            sources.append({
                "title": r.title,
                "url": r.url,
                "source": r.source_name,
                "score": r.score,
                "domain": r.domain,
                "published_date": r.published_date,
                "reliability": round(reliability, 3),
                "verified": reliability >= self.settings.min_source_reliability,
            })

        trusted_domains = {
            r.domain for r in ranked_results[:6]
            if scorer.domain_reliability(r.domain) >= self.settings.min_source_reliability
        }
        verification_summary = {
            "strict_mode": self.settings.strict_verified_mode,
            "trusted_source_count": len(trusted_domains),
            "multi_source_news_verified": (
                intent != QueryIntent.LATEST_NEWS
                or not self.settings.require_multi_source_for_news
                or len(trusted_domains) >= 2
            ),
        }

        payload = {
            "answer": answer,
            "sources": sources,
            "images": list(set(all_images))[:5],
            "language": detected_lang,
            "intent": intent,
            "providers_queried": list(set(k.split("_")[0] for k in responses.keys())),
            "schemes": [],
            "state_detected": final_state,
            "verification": verification_summary,
            "cache_hit": False,
        }

        cache.put(
            query=english_query,
            language=detected_lang,
            intent=intent,
            state_code=state_code,
            payload=payload,
            profile_fingerprint=profile_fingerprint,
        )
        return payload

    # ──────────────────────────────────────────────────────────────────────────
    # Multi-Query Fan-Out
    # ──────────────────────────────────────────────────────────────────────────

    def _build_profile_fingerprint(
        self,
        profile: dict,
        sector: str | None,
        user_types: list[str],
    ) -> str:
        """
        Build a stable, privacy-conscious cache fingerprint.
        Avoid full session leakage while preventing wrong cross-user cache hits.
        """
        if not profile and not sector and not user_types:
            return ""

        allowed_keys = {
            "state",
            "state_code",
            "age",
            "gender",
            "income_per_year",
            "caste_category",
            "occupation",
            "bpl_card",
            "landholding_acres",
            "family_size",
            "education",
        }
        reduced_profile = {
            key: profile.get(key)
            for key in sorted(allowed_keys)
            if key in profile and profile.get(key) is not None
        }

        payload = {
            "profile": reduced_profile,
            "sector": sector or "",
            "user_types": sorted(user_types or []),
        }
        return json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))

    def _expand_queries(
        self,
        base_query: str,
        state: dict | None,
        sector: str | None,
        user_types: list[str],
        year_hint: str,
    ) -> list[str]:
        """
        Expand one user query into up to 4 targeted sub-queries.
        All sub-queries are fired in parallel to gather maximum research data.
        """
        state_name = state["name"] if state else "India"
        state_code = state["code"] if state else ""
        queries = [base_query]  # Always include the original

        # Sub-query 1: State-specific official scheme query
        if state:
            q1 = f"{state_name} government {base_query} scheme eligibility {year_hint} official"
            queries.append(q1)

        # Sub-query 2: Central government + sector focus
        if sector:
            sector_terms = {
                "agricultural": "PM-KISAN agricultural land farming",
                "housing": "PMAY housing home construction",
                "education": "scholarship student education fee",
                "health": "Ayushman Bharat health insurance",
                "employment": "NREGA MUDRA skill employment",
                "social_security": "pension widow disabled BPL welfare",
                "industrial": "MSME industrial SIPCOT startup",
            }
            sector_focus = sector_terms.get(sector, sector)
            q2 = f"India central government {sector_focus} subsidy scheme {year_hint}"
            queries.append(q2)
        else:
            q2 = f"India central government {base_query} {year_hint} scheme benefits"
            queries.append(q2)

        # Sub-query 3: User-type focused query
        if user_types:
            user_focus = " ".join(user_types[:2]).replace("_", " ")
            q3 = f"{state_name} {user_focus} {base_query} scheme documents application link"
            queries.append(q3)

        return queries[:4]  # Cap at 4 sub-queries

    # ──────────────────────────────────────────────────────────────────────────
    # Context Builder
    # ──────────────────────────────────────────────────────────────────────────

    def _build_context(
        self,
        results: list[SearchResult],
        ai_answers: list[str],
        images: list[str],
        state: dict | None,
        sector: str | None,
        user_types: list[str],
        user_profile: dict,
        intent: str | None = None,
        strict_verified: bool = False,
    ) -> str:
        """Build rich, structured LLM context."""
        parts = []
        scorer = get_quality_scorer()

        # ── Research Directive (tells LLM what to focus on) ──
        state_name = state["name"] if state else "India (all states)"
        current_year = datetime.now(timezone.utc).year
        directive = f"""═══ RESEARCH DIRECTIVE ═══
LOCATION: {state_name}
SECTOR: {sector or "General Government Schemes"}
USER TYPE: {", ".join(user_types) if user_types else "General Citizen"}
INTENT: {intent or "scheme_discovery"}
STRICT VERIFICATION MODE: {"ON" if strict_verified else "OFF"}
YEAR: {current_year} (use latest data available)

INSTRUCTIONS:
1. Separate response into DISTINCT sections: State-level schemes, Central government schemes.
2. If sector is 'agricultural', also add: SC/ST specific, Irrigation, Land development.
3. Include EXACT ₹ amounts, % subsidies, income ceilings, age limits — no approximations.
4. List SPECIFIC documents actually required for each scheme (not generic Aadhaar + cert).
5. Include official portal URLs and helpline numbers.
6. Add a "How to Apply — Step by Step" section at the end.
7. Add a "Key Requirements to Verify Before Applying" section.
8. Cite each major claim with source URL and publication date.
9. If trustworthy sources are insufficient, explicitly say verification is required.
═══════════════════════════════"""
        parts.append(directive)

        # ── Known User Profile ──
        if user_profile:
            profile_lines = ["═══ KNOWN USER PROFILE ═══"]
            for k, v in user_profile.items():
                profile_lines.append(f"  {k}: {v}")
            profile_lines.append("Use this profile to prioritize the most relevant schemes.")
            parts.append("\n".join(profile_lines))

        # ── AI Research Insights ──
        if ai_answers:
            parts.append("\n═══ AI RESEARCH INSIGHTS ═══")
            for ans in ai_answers[:4]:
                parts.append(f"{ans}\n")

        # ── Ranked Search Results ──
        if results:
            parts.append("\n═══ TOP RESEARCH SOURCES ═══")
            for i, r in enumerate(results[:10], 1):
                reliability = scorer.domain_reliability(r.domain)
                verify_status = (
                    "VERIFIED"
                    if reliability >= self.settings.min_source_reliability
                    else "UNVERIFIED"
                )
                if ".gov" in r.domain:
                    trust = "🏛️ GOVT"
                elif "wiki" in r.domain:
                    trust = "📚 WIKI"
                else:
                    trust = "📰 NEWS"

                parts.append(
                    f"\n--- SOURCE {i} [{trust} | {r.source_name}] "
                    f"(Score: {r.score} | Reliability: {reliability:.2f} | {verify_status}) ---\n"
                    f"Title: {r.title}\n"
                    f"URL: {r.url}\n"
                    f"Published: {r.published_date or 'unknown'}\n"
                    f"Content: {r.content[:3000]}\n"
                )
        elif strict_verified:
            parts.append(
                "\nNo verified external sources were available. "
                "State this clearly and ask the user to verify via official portals."
            )

        # ── Images ──
        if images:
            parts.append("\n═══ AVAILABLE IMAGES ═══")
            for img in images[:4]:
                parts.append(f"- {img}")

        return "\n".join(parts)

    # ──────────────────────────────────────────────────────────────────────────
    # Profile Mining
    # ──────────────────────────────────────────────────────────────────────────

    def _mine_profile_from_query(self, query: str, session_id: str) -> None:
        """
        Extract profile data from user's natural language message.
        Example: "I am a 25 year old SC farmer in Tamil Nadu with 2 acres"
        """
        from app.services import session_store
        normalized = query.lower()
        updates = {}

        # Age
        age_match = re.search(r"\b(\d{1,2})\s*(years?\s*old|yr\s*old|age)\b", normalized)
        if not age_match:
            age_match = re.search(r"\baged?\s+(\d{1,2})\b", normalized)
        if age_match:
            try:
                age = int(age_match.group(1))
                if 5 <= age <= 100:
                    updates["age"] = age
            except ValueError:
                pass

        # Income (handles "1 lakh", "50000", "50k")
        income_match = re.search(
            r"\b(\d[\d,]*\.?\d*)\s*(lakh|lac|lakhs|lacs|k|thousand)?\s*(per year|annually|pa|income)?\b",
            normalized
        )
        if income_match:
            try:
                raw = float(income_match.group(1).replace(",", ""))
                unit = (income_match.group(2) or "").lower()
                if "lakh" in unit or "lac" in unit:
                    raw *= 100000
                elif unit == "k":
                    raw *= 1000
                if 1000 <= raw <= 10000000:
                    updates["income_per_year"] = raw
            except (ValueError, AttributeError):
                pass

        # Caste
        if re.search(r"\bsc\b|\bscheduled caste\b|\bdalit\b", normalized):
            updates["caste_category"] = "SC"
        elif re.search(r"\bst\b|\bscheduled tribe\b|\btribal\b|\badivasi\b", normalized):
            updates["caste_category"] = "ST"
        elif re.search(r"\bobc\b|\bother backward\b", normalized):
            updates["caste_category"] = "OBC"
        elif re.search(r"\bews\b|\beconomically weaker\b", normalized):
            updates["caste_category"] = "EWS"

        # Occupation
        if re.search(r"\bfarmer\b|\bkisan\b|\bagriculture\b", normalized):
            updates["occupation"] = "farmer"
        elif re.search(r"\bstudent\b", normalized):
            updates["occupation"] = "student"
        elif re.search(r"\bdaily wage\b|\blabour\b|\blabourer\b", normalized):
            updates["occupation"] = "daily_wage_worker"

        # Gender
        if re.search(r"\bwoman\b|\bfemale\b|\bmahila\b|\bgirl\b|\bher\b\s+name", normalized):
            updates["gender"] = "female"
        elif re.search(r"\bman\b|\bmale\b|\bhe\s+is\b", normalized):
            updates["gender"] = "male"

        # BPL
        if re.search(r"\bbpl\b|\bbelow poverty\b|\bration card\b", normalized):
            updates["bpl_card"] = True

        # Land holding
        land_match = re.search(r"(\d+\.?\d*)\s*acre", normalized)
        if land_match:
            try:
                updates["landholding_acres"] = float(land_match.group(1))
            except ValueError:
                pass

        if updates:
            session_store.update_profile(session_id, updates)
            logger.info(f"👤 Mined profile updates for {session_id}: {updates}")

    # ──────────────────────────────────────────────────────────────────────────
    # Greeting Handler
    # ──────────────────────────────────────────────────────────────────────────

    async def _handle_greeting(self, query: str, user_id: str, language: str) -> dict:
        """Handle greetings without any API calls."""
        llm = self._get_llm()
        answer = await llm.generate(
            user_query=query,
            context=GREETING_CONTEXT,
            chat_history=[],
            language=language if language != "auto" else "en",
            is_greeting=True,
        )
        return {
            "answer": answer,
            "sources": [],
            "images": [],
            "language": language if language != "auto" else "en",
            "intent": QueryIntent.GREETING,
            "providers_queried": [],
            "schemes": [],
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Translation Helpers
    # ──────────────────────────────────────────────────────────────────────────

    async def _translate_to_english(self, text: str, source_lang: str) -> tuple[str, str]:
        try:
            from app.services.translation_service import get_translation_service
            translator = get_translation_service()
            english = translator.translate(text, source=source_lang, target="en")
            return english, source_lang
        except Exception as e:
            logger.warning(f"⚠️ Translation failed: {e}")
            return text, source_lang

    async def _detect_and_translate(self, text: str) -> tuple[str, str]:
        try:
            from app.services.translation_service import get_translation_service
            translator = get_translation_service()
            detected = translator.detect_language(text)
            if detected != "en":
                english = translator.translate(text, source=detected, target="en")
                return english, detected
            return text, "en"
        except Exception:
            return text, "en"

    async def _translate_response(self, text: str, target_lang: str) -> str:
        try:
            from app.services.translation_service import get_translation_service
            translator = get_translation_service()
            return translator.translate(text, source="en", target=target_lang)
        except Exception:
            return text

    # ──────────────────────────────────────────────────────────────────────────
    # Audio Pipeline
    # ──────────────────────────────────────────────────────────────────────────

    async def query_audio(self, audio_bytes: bytes, user_id: str = None, language: str = "auto") -> dict:
        """Voice pipeline: Audio → STT → Query → TTS → Audio."""
        from app.services.voice_service import get_voice_service
        voice = get_voice_service()

        transcribed_text, detected_language = await voice.transcribe(audio_bytes)
        logger.info(f"🎙️ Transcribed: '{transcribed_text[:80]}...' lang={detected_language}")

        result = await self.query(
            user_query=transcribed_text,
            user_id=user_id,
            language=detected_language,
        )

        audio_path = await voice.synthesize(result["answer"], language=detected_language)
        result["audio_url"] = audio_path
        result["transcribed_text"] = transcribed_text
        return result


# --- Singleton ---
_aggregator: APIAggregator | None = None


def get_api_aggregator() -> APIAggregator:
    """Returns a cached API Aggregator instance."""
    global _aggregator
    if _aggregator is None:
        _aggregator = APIAggregator()
    return _aggregator
