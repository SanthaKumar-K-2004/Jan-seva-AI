"""
Jan-Seva AI — RAG (Retrieval Augmented Generation) Service
Enterprise-grade: each pipeline step has independent error handling.
Lazy initialization of heavy dependencies (embedder, LLM).
"""

from app.core.supabase_client import get_supabase_client, vector_search
from app.utils.logger import logger
import traceback
import re

# ── Greeting Detection ────────────────────────────────────────
# These patterns match common greetings in English and Indian languages.
# When detected, we skip the entire RAG pipeline and go straight to LLM.
GREETING_PATTERNS = {
    # English
    "hi", "hello", "hey", "hii", "hiii", "hiiii", "helo", "hola",
    "yo", "sup", "howdy", "greetings", "good morning", "good afternoon",
    "good evening", "good night", "gm", "gn", "morning", "evening",
    "what's up", "whats up", "wassup", "how are you", "how r u",
    "how are u", "how do you do", "nice to meet you",
    # Hindi
    "namaste", "namaskar", "namaskaaram", "pranam", "pranaam",
    "नमस्ते", "नमस्कार", "प्रणाम", "राम राम", "जय हिंद",
    # Tamil
    "vanakkam", "வணக்கம்",
    # Telugu
    "namaskaram", "నమస్కారం",
    # Kannada
    "namaskara", "ನಮಸ್ಕಾರ",
    # Malayalam
    "namaskaram", "നമസ്കാരം",
    # Bengali
    "nomoshkar", "নমস্কার",
    # Marathi
    "namaskar", "नमस्कार",
    # Gujarati
    "kem cho", "કેમ છો",
    # Punjabi
    "sat sri akal", "ਸਤ ਸ੍ਰੀ ਅਕਾਲ",
    # Odia
    "namaskar", "ନମସ୍କାର",
    # Urdu
    "assalam alaikum", "salam", "السلام علیکم",
}


def _is_greeting(text: str) -> bool:
    """
    Check if the user message is a greeting.
    Handles exact matches and short phrases that start with greeting words.
    """
    cleaned = text.strip().lower()
    # Remove punctuation for matching
    cleaned = re.sub(r'[!?.,:;\'\"]+', '', cleaned).strip()

    # Exact match
    if cleaned in GREETING_PATTERNS:
        return True

    # Short messages (1-4 words) starting with a greeting word
    words = cleaned.split()
    if len(words) <= 4 and words[0] in GREETING_PATTERNS:
        return True

    # Check multi-word greetings
    for greeting in GREETING_PATTERNS:
        if ' ' in greeting and cleaned.startswith(greeting):
            return True

    return False


GREETING_CONTEXT = (
    "The user has just greeted you. This is the START of a conversation. "
    "Respond with a warm, friendly, and concise welcome. Introduce yourself as Jan-Seva AI, "
    "a government scheme assistant for India. Briefly mention 2-3 things you can help with "
    "(like finding eligible schemes, application guidance, documents needed). "
    "Keep the response SHORT (3-5 sentences max). End by asking how you can help them today. "
    "Do NOT give a dictionary definition of the greeting word. "
    "Do NOT search the web or cite sources. Just be friendly and welcoming."
)


class RAGService:
    """
    RAG Pipeline with graceful degradation.
    Dependencies are lazily initialized on first use.
    """

    def __init__(self):
        self._llm = None
        self._embedder = None

    def _get_llm(self):
        """Lazy-load LLM client."""
        if self._llm is None:
            from app.core.llm_client import get_llm_client
            self._llm = get_llm_client()
        return self._llm

    def _get_embedder(self):
        """Lazy-load embedding client."""
        if self._embedder is None:
            from app.core.embedding_client import get_embedding_client
            self._embedder = get_embedding_client()
        return self._embedder

    def _get_web_search(self):
        """Lazy-load web search service."""
        from app.services.web_search_service import get_web_search_service
        return get_web_search_service()

    async def query(self, user_query: str, user_id: str = None, language: str = "en") -> dict:
        """
        Main RAG query pipeline with per-step error isolation.
        Returns: {"answer": str, "sources": list[str], "schemes": list[dict]}
        """
        detected_lang = language
        english_query = user_query

        # ── Step 0: Greeting Detection (fast path) ──
        # Skip the entire RAG pipeline for simple greetings
        if _is_greeting(user_query):
            logger.info(f"👋 Greeting detected: '{user_query}' — using fast path (skipping RAG)")
            llm = self._get_llm()
            answer = await llm.generate(
                user_query=user_query,
                context=GREETING_CONTEXT,
                chat_history=[],
                language=language if language != "auto" else "en",
                is_greeting=True,
            )

            # Save chat history
            if user_id:
                try:
                    await self._save_chat(user_id, user_query, answer, language if language != "auto" else "en")
                except Exception as e:
                    logger.warning(f"⚠️ Chat save failed: {e}")

            return {
                "answer": answer,
                "sources": [],
                "chunks_used": 0,
                "language": language if language != "auto" else "en",
                "schemes": [],
            }

        # ── Step 1: Translation (non-critical — skip if fails) ──
        if language != "en":
            try:
                from app.services.translation_service import get_translation_service
                translator = get_translation_service()

                if language == "auto":
                    detected_lang = translator.detect_language(user_query)
                    if detected_lang != "en":
                        english_query = translator.translate(user_query, source=detected_lang, target="en")
                else:
                    english_query = translator.translate(user_query, source=language, target="en")
                    detected_lang = language
            except Exception as e:
                logger.warning(f"⚠️ Translation failed (proceeding with original text): {e}")
                english_query = user_query
                detected_lang = language if language != "auto" else "en"

        # ── Step 2: Embedding (required for vector search) ──
        query_embedding = None
        try:
            embedder = self._get_embedder()
            query_embedding = embedder.embed_text(english_query)
        except Exception as e:
            logger.warning(f"⚠️ Embedding failed (will skip vector search): {e}")

        # ── Step 3: Vector search (skip if no embedding) ──
        chunks = []
        if query_embedding is not None:
            try:
                chunks = await vector_search(query_embedding, match_count=8)
            except Exception as e:
                logger.warning(f"⚠️ Vector search failed (proceeding without context): {e}")

        # ── Step 4: Build context from retrieved chunks ──
        context_parts = []
        sources = []
        scheme_ids = set()

        for chunk in chunks:
            context_parts.append(chunk.get("chunk_text", ""))
            source = chunk.get("metadata", {}).get("source_name", "")
            if source and source not in sources:
                sources.append(source)
            sid = chunk.get("scheme_id")
            if sid:
                scheme_ids.add(sid)

        # ── Step 5: Enrich with scheme metadata (non-critical) ──
        scheme_details = []
        if scheme_ids:
            try:
                scheme_details = await self._get_scheme_metadata(list(scheme_ids)[:8])
                for sd in scheme_details:
                    cat = sd.get("category", [])
                    if isinstance(cat, list):
                        cat = ", ".join(cat)
                    meta_text = (
                        f"\n\n📋 SCHEME: {sd['name']}\n"
                        f"State: {sd.get('state', 'Central')}\n"
                        f"Ministry: {sd.get('ministry', 'N/A')}\n"
                        f"Category: {cat}\n"
                        f"Benefits: {sd.get('benefits', 'N/A')}\n"
                        f"Description: {sd.get('description', '')}\n"
                    )
                    # Add eligibility if available
                    if sd.get("eligibility"):
                        meta_text += f"Eligibility: {sd['eligibility']}\n"
                    if sd.get("documents_required"):
                        meta_text += f"Documents Required: {sd['documents_required']}\n"
                    if sd.get("application_mode"):
                        meta_text += f"How to Apply: {sd['application_mode']}\n"
                    if sd.get("source_url"):
                        meta_text += f"Official Portal: {sd['source_url']}\n"
                    context_parts.append(meta_text)
            except Exception as e:
                logger.warning(f"⚠️ Scheme metadata fetch failed: {e}")

        # ── Step 5.5: Web Search (Augmentation) ──
        # Only trigger web search when:
        # 1. Query explicitly asks for "new/latest" info
        # 2. Query mentions a specific year (2024, 2025, 2026)
        # 3. Vector search found nothing AND the query is substantial (>3 words)
        # Do NOT trigger for very short or generic queries
        freshness_keywords = ["new", "latest", "current", "recent", "update", "2024", "2025", "2026"]
        query_words = english_query.lower().split()
        has_freshness_keyword = any(k in english_query.lower() for k in freshness_keywords)
        is_substantial_query = len(query_words) > 3

        needs_search = has_freshness_keyword or (not context_parts and is_substantial_query)

        if needs_search:
            try:
                web_search = self._get_web_search()
                search_results = await web_search.search(english_query, limit=4)
                if search_results:
                    context_parts.append(search_results)
                    sources.append("Web Search (DuckDuckGo)")
            except Exception as e:
                logger.warning(f"⚠️ Web search augmentation failed: {e}")

        context = "\n\n---\n\n".join(context_parts) if context_parts else ""

        # ── Step 6: Chat history (non-critical) ──
        chat_history = []
        if user_id:
            try:
                chat_history = await self._get_chat_history(user_id)
            except Exception as e:
                logger.warning(f"⚠️ Chat history fetch failed: {e}")

        # ── Step 7: LLM generation ──
        # If this raises, chat.py Tier 2 will handle it
        llm = self._get_llm()
        answer = await llm.generate(
            user_query=english_query,
            context=context if context else "No context available from the database. Answer based on your general knowledge about Indian government schemes.",
            chat_history=chat_history,
            language=detected_lang,
        )

        # ── Step 8: Translate back (non-critical) ──
        if detected_lang != "en":
            try:
                from app.services.translation_service import get_translation_service
                translator = get_translation_service()
                answer = translator.translate(answer, source="en", target=detected_lang)
            except Exception as e:
                logger.warning(f"⚠️ Response translation failed (returning English): {e}")

        # ── Step 9: Save chat (fire-and-forget) ──
        if user_id:
            try:
                await self._save_chat(user_id, user_query, answer, detected_lang)
            except Exception as e:
                logger.warning(f"⚠️ Chat save failed: {e}")

        return {
            "answer": answer,
            "sources": sources,
            "chunks_used": len(context_parts),
            "language": detected_lang,
            "schemes": [
                {"id": s.get("id"), "name": s.get("name"), "benefits": s.get("benefits", "")}
                for s in scheme_details
            ],
        }

    async def query_audio(self, audio_bytes: bytes, user_id: str = None, language: str = "auto") -> dict:
        """Voice RAG pipeline."""
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
        result["language"] = detected_language
        return result

    async def search(self, query: str, limit: int = 10) -> list[dict]:
        """Search schemes by vector similarity."""
        embedder = self._get_embedder()
        query_embedding = embedder.embed_text(query)
        results = await vector_search(query_embedding, match_count=limit)
        return results

    async def _get_scheme_metadata(self, scheme_ids: list[str]) -> list[dict]:
        """Fetch scheme details for context enrichment."""
        client = get_supabase_client()
        try:
            result = client.table("schemes").select(
                "id, name, category, benefits, description, ministry, state, source_url, eligibility, documents_required, application_mode"
            ).in_("id", scheme_ids).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Failed to fetch scheme metadata: {e}")
            return []

    async def _save_chat(self, user_id: str, user_msg: str, bot_msg: str, language: str):
        """Save conversation to chat_history table."""
        client = get_supabase_client()
        try:
            client.table("chat_history").insert([
                {"user_id": user_id, "role": "user", "content": user_msg, "language": language},
                {"user_id": user_id, "role": "assistant", "content": bot_msg, "language": language},
            ]).execute()
        except Exception as e:
            logger.warning(f"Failed to save chat history: {e}")

    async def _get_chat_history(self, user_id: str, limit: int = 6) -> list:
        """Fetch recent chat history for context."""
        client = get_supabase_client()
        try:
            response = client.table("chat_history") \
                .select("role, content") \
                .eq("user_id", user_id) \
                .order("created_at", desc=True) \
                .limit(limit) \
                .execute()
            history = response.data[::-1] if response.data else []
            return history
        except Exception as e:
            logger.warning(f"Failed to fetch chat history: {e}")
            return []


# --- Singleton ---
_rag_service: RAGService | None = None


def get_rag_service() -> RAGService:
    """Returns a cached RAG service instance."""
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service
