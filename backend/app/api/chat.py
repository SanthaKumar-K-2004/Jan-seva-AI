"""
Jan-Seva AI — Chat API Router
Handles text and audio chat with:
  1. IP-based location detection (auto state context)
  2. Session management (user profile + chat history)
  3. Topic moderation (warn → block after 3 violations)
  4. Multi-API aggregation pipeline
  5. 3-tier fallback (aggregator → direct LLM → static)
"""

from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from app.models.chat import ChatTextRequest, ChatResponse
from app.services.api_aggregator import get_api_aggregator
from app.utils.logger import logger
import os
import traceback

router = APIRouter()


FALLBACK_MESSAGE = (
    "I apologize, but I'm currently experiencing technical difficulties "
    "and cannot process your request right now.\n\n"
    "**In the meantime, you can:**\n"
    "- Visit [MyScheme.gov.in](https://www.myscheme.gov.in) to search for government schemes\n"
    "- Call the national helpline **1800-11-0031** for scheme-related queries\n"
    "- Try again in a few minutes\n\n"
    "We are working to restore full service as quickly as possible. 🙏"
)


def _resolve_session_id(request: ChatTextRequest) -> str:
    """Derive a stable session identifier."""
    return (
        request.session_id
        or request.conversation_id
        or request.user_id
        or "anonymous"
    )


@router.post("/text", response_model=ChatResponse)
async def chat_text(chat_request: ChatTextRequest, request: Request):
    """
    Text-based chat endpoint.
    Full pipeline:
      IP detection → topic guard → block check → API aggregation → LLM
    """
    from app.services.topic_guard import get_topic_guard, TopicVerdict
    from app.services.topic_guard import get_warning_message, get_block_message, get_hard_block_message
    from app.services.session_store import is_blocked, issue_warning, set_state_from_ip
    from app.services.location_service import get_location_service

    session_id = _resolve_session_id(chat_request)
    message = chat_request.message.strip()

    # ── 0. IP → State Resolution ─────────────────────────────────────────────
    client_ip = chat_request.ip_address or request.client.host
    resolved_state = None
    # Honour explicit state from client first
    if chat_request.user_state:
        resolved_state_name = chat_request.user_state
    else:
        try:
            location_svc = get_location_service()
            state_info = await location_svc.get_state_from_ip(client_ip)
            if state_info:
                set_state_from_ip(session_id, state_info)
                resolved_state = state_info
                logger.info(f"📍 Session {session_id}: state = {state_info['name']}")
        except Exception as e:
            logger.warning(f"📍 Location lookup failed: {e}")

    # ── 1. Topic Guard ────────────────────────────────────────────────────────
    guard = get_topic_guard()
    verdict = guard.classify(message)

    if verdict == TopicVerdict.BLOCK:
        return ChatResponse(
            reply=get_hard_block_message(),
            is_blocked=True,
        )

    # ── 2. Block Status Check ─────────────────────────────────────────────────
    blocked, remaining = is_blocked(session_id)
    if blocked:
        return ChatResponse(
            reply=get_block_message(remaining),
            is_blocked=True,
        )

    # ── 3. Off-Topic Warning ──────────────────────────────────────────────────
    if verdict == TopicVerdict.WARN:
        warn_num, now_blocked = issue_warning(session_id)
        if now_blocked:
            return ChatResponse(
                reply=get_block_message(3600),
                is_blocked=True,
                warning_count=warn_num,
            )
        return ChatResponse(
            reply=get_warning_message(warn_num),
            warning_count=warn_num,
        )

    # ── 4. Full API Aggregation Pipeline ──────────────────────────────────────
    try:
        aggregator = get_api_aggregator()
        result = await aggregator.query(
            user_query=message,
            user_id=chat_request.user_id,
            language=chat_request.language,
            session_id=session_id,
            resolved_state=resolved_state,
        )
        return ChatResponse(
            reply=result["answer"],
            sources=result.get("sources", []),
            images=result.get("images", []),
            language=result.get("language", chat_request.language),
            schemes=result.get("schemes", []),
        )
    except Exception as agg_err:
        logger.error(f"❌ API Aggregation failed: {agg_err}\n{traceback.format_exc()}")

    # ── 5. Tier 2: Direct LLM fallback ───────────────────────────────────────
    try:
        from app.core.llm_client import get_llm_client
        llm = get_llm_client()
        fallback_answer = await llm.generate(
            user_query=message,
            context=(
                "Your search APIs are temporarily unavailable. "
                "Answer the user's question using your general knowledge about "
                "Indian government schemes. If you are unsure, say so honestly and suggest "
                "the user visit https://www.myscheme.gov.in or https://www.india.gov.in."
            ),
            chat_history=[],
            language=chat_request.language,
        )
        return ChatResponse(
            reply=fallback_answer,
            sources=[],
            images=[],
            language=chat_request.language,
            schemes=[],
        )
    except Exception as llm_err:
        logger.error(f"❌ LLM fallback also failed: {llm_err}\n{traceback.format_exc()}")

    # ── 6. Tier 3: Static fallback ────────────────────────────────────────────
    return ChatResponse(
        reply=FALLBACK_MESSAGE,
        sources=[],
        images=[],
        language=chat_request.language,
        schemes=[],
    )


@router.post("/audio")
async def chat_audio(
    audio: UploadFile = File(...),
    user_id: str = Form(default=None),
    language: str = Form(default="auto"),
    slow: bool = Form(default=False),
    session_id: str = Form(default=None),
):
    """Voice-based chat: Audio → STT → Multi-API Search → LLM → TTS → Audio."""
    try:
        if audio.size and audio.size > 10 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Audio file too large (max 10MB)")

        audio_bytes = await audio.read()
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="Empty audio file")

        aggregator = get_api_aggregator()
        result = await aggregator.query_audio(
            audio_bytes=audio_bytes,
            user_id=user_id,
            language=language,
        )

        audio_path = result.get("audio_url")
        if audio_path and os.path.exists(audio_path):
            return FileResponse(
                audio_path,
                media_type="audio/mpeg",
                headers={
                    "X-Reply-Text": result.get("answer", "")[:500],
                    "X-Language": result.get("language", "en"),
                    "X-Transcribed": result.get("transcribed_text", "")[:200],
                    "X-Sources": ",".join([s.get("title", "") for s in result.get("sources", [])]),
                },
            )

        return {
            "reply": result["answer"],
            "sources": result.get("sources", []),
            "images": result.get("images", []),
            "language": result.get("language", language),
            "transcribed_text": result.get("transcribed_text", ""),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Chat audio error: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to process audio. Please try again.")


@router.get("/languages")
async def supported_languages():
    """Return all supported languages for chat."""
    try:
        from app.services.translation_service import INDIAN_LANGUAGES
        return {"languages": INDIAN_LANGUAGES, "default": "en"}
    except ImportError:
        return {
            "languages": [
                {"code": "en", "name": "English"},
                {"code": "hi", "name": "Hindi"},
            ],
            "default": "en",
        }
