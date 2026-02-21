"""
Jan-Seva AI — WhatsApp Webhook Router (Enhanced)
Handles incoming messages (Text, Audio, Location) from Meta Cloud API.
"""

from fastapi import APIRouter, Request, Query, BackgroundTasks
from app.config import get_settings
from app.utils.logger import logger
from app.services.api_aggregator import get_api_aggregator
from app.services.voice_service import get_voice_service
import httpx

router = APIRouter()


@router.get("/whatsapp")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """WhatsApp webhook verification (required by Meta)."""
    settings = get_settings()
    if hub_mode == "subscribe" and hub_token == settings.whatsapp_verify_token:
        return int(hub_challenge)
    return {"error": "Verification failed"}


@router.post("/whatsapp")
async def receive_message(request: Request, background_tasks: BackgroundTasks):
    """
    Receive incoming WhatsApp messages.
    Supports:
    - Text: Standard RAG query
    - Audio: Transcribe → RAG query
    - Location: Find nearby schemes/centers (placeholder)
    """
    body = await request.json()

    # Extract message from webhook payload
    try:
        entry = body.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if not messages:
            return {"status": "no_messages"}

        message = messages[0]
        phone_number = message.get("from", "")
        message_type = message.get("type", "")
        
        # Helper to send processing status
        # background_tasks.add_task(_send_whatsapp_status, phone_number, "reading")

        if message_type == "text":
            user_text = message["text"]["body"]
            await _handle_text_message(phone_number, user_text)

        elif message_type == "audio":
            audio_id = message["audio"]["id"]
            await _handle_audio_message(phone_number, audio_id)

        elif message_type == "location":
            location = message["location"]
            await _handle_location_message(phone_number, location)

        return {"status": "processed"}

    except Exception as e:
        logger.error(f"❌ WhatsApp webhook error: {e}")
        return {"status": "error", "message": str(e)}


async def _handle_text_message(phone: str, text: str):
    """Process text message through RAG."""
    aggregator = get_api_aggregator()
    result = await aggregator.query(
        user_query=text,
        user_id=phone,
        language="auto",
    )
    # Reply with answer
    await _send_whatsapp_reply(phone, result["answer"])


async def _handle_audio_message(phone: str, audio_id: str):
    """Process audio message: Download → Transcribe → RAG."""
    voice = get_voice_service()
    aggregator = get_api_aggregator()
    settings = get_settings()

    try:
        # Step 1: Get media URL
        async with httpx.AsyncClient() as client:
            url_resp = await client.get(
                f"https://graph.facebook.com/v18.0/{audio_id}",
                headers={"Authorization": f"Bearer {settings.whatsapp_access_token}"},
            )
            media_url = url_resp.json().get("url")
            
            # Step 2: Download binary
            media_resp = await client.get(
                media_url,
                headers={"Authorization": f"Bearer {settings.whatsapp_access_token}"},
            )
            audio_bytes = media_resp.content

        # Step 3: Transcribe
        text, lang = await voice.transcribe(audio_bytes)
        
        # Step 4: RAG Query
        result = await aggregator.query(
            user_query=text,
            user_id=phone,
            language=lang,
        )

        # Step 5: Reply
        # Optional: Send audio reply back? For now, text reply is safer/cheaper
        response_text = f"🎤 *You said:* {text}\n\n🤖 *Jan-Seva:* {result['answer']}"
        await _send_whatsapp_reply(phone, response_text)

    except Exception as e:
        logger.error(f"❌ WhatsApp audio processing failed: {e}")
        await _send_whatsapp_reply(phone, "Sorry, I couldn't understand that audio message. Please try sending text.")


async def _handle_location_message(phone: str, location: dict):
    """Handle geo-location for nearby centers."""
    lat = location.get("latitude")
    lng = location.get("longitude")
    # Placeholder: In real app, query PostGIS/Supabase for nearest CSC
    msg = f"📍 Received your location ({lat}, {lng}). Finding nearest Jan-Seva Kendra...\n\n(This feature is coming soon!)"
    await _send_whatsapp_reply(phone, msg)


async def _send_whatsapp_reply(to_number: str, message: str):
    """Send a reply message via WhatsApp Cloud API."""
    settings = get_settings()
    url = f"https://graph.facebook.com/v18.0/{settings.whatsapp_phone_number_id}/messages"

    async with httpx.AsyncClient() as client:
        await client.post(
            url,
            headers={"Authorization": f"Bearer {settings.whatsapp_access_token}"},
            json={
                "messaging_product": "whatsapp",
                "to": to_number,
                "type": "text",
                "text": {"body": message},
            },
        )
