"""
Jan-Seva AI — Voice Service (Enhanced)
Whisper (STT) + Edge-TTS (TTS) for all major Indian languages.
All free, no paid APIs.
"""

import tempfile
import os
import edge_tts
from app.utils.logger import logger


class VoiceService:
    """
    Voice Pipeline:
    Audio → Whisper STT → Text
    Text → Edge-TTS → Audio
    """

    def __init__(self):
        self._whisper_model = None

    def _load_whisper(self):
        """Lazy-load Whisper model (downloads on first use ~73MB for base)."""
        if self._whisper_model is None:
            import whisper
            from app.config import get_settings

            settings = get_settings()
            model_size = settings.whisper_model_size
            logger.info(f"📦 Loading Whisper model: {model_size}...")
            self._whisper_model = whisper.load_model(model_size)
            logger.info("✅ Whisper model loaded.")
        return self._whisper_model

    async def transcribe(self, audio_bytes: bytes) -> tuple[str, str]:
        """
        Transcribe audio bytes to text using Whisper.
        Returns: (transcribed_text, detected_language)
        """
        # Save to temp file (Whisper needs a file path)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes)
            temp_path = f.name

        try:
            model = self._load_whisper()
            result = model.transcribe(temp_path)
            text = result.get("text", "").strip()
            language = result.get("language", "en")
            logger.info(f"🎙️ STT: '{text[:50]}...' (lang={language})")
            return text, language
        except Exception as e:
            logger.error(f"❌ Whisper transcription failed: {e}")
            raise
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    async def synthesize(self, text: str, language: str = "en", slow: bool = False) -> str:
        """
        Convert text to speech using Edge-TTS (Microsoft's free TTS).
        Returns: path to generated MP3 audio file.
        """
        voice = self._get_voice(language)
        rate = "-30%" if slow else "+0%"  # Slow mode for elders

        # Truncate very long texts (Edge-TTS has limits)
        if len(text) > 3000:
            text = text[:3000] + "..."

        try:
            output_path = tempfile.mktemp(suffix=".mp3")
            communicate = edge_tts.Communicate(text, voice, rate=rate)
            await communicate.save(output_path)
            logger.info(f"🔊 TTS: Generated audio ({language}) → {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"❌ Edge-TTS failed: {e}")
            raise

    def _get_voice(self, language: str) -> str:
        """Map language codes to Edge-TTS voice names (Indian variants)."""
        voice_map = {
            # --- Major Indian Languages ---
            "en": "en-IN-NeerjaNeural",        # Indian English (Female)
            "hi": "hi-IN-SwaraNeural",          # Hindi (Female)
            "ta": "ta-IN-PallaviNeural",        # Tamil (Female)
            "te": "te-IN-ShrutiNeural",         # Telugu (Female)
            "kn": "kn-IN-SapnaNeural",          # Kannada (Female)
            "ml": "ml-IN-SobhanaNeural",        # Malayalam (Female)
            "bn": "bn-IN-TanishaaNeural",       # Bengali (Female)
            "mr": "mr-IN-AarohiNeural",         # Marathi (Female)
            "gu": "gu-IN-DhwaniNeural",         # Gujarati (Female)
            "pa": "pa-IN-GurpreetNeural",       # Punjabi (Male — only option)
            "ur": "ur-IN-GulNeural",            # Urdu (Female)
            # --- Male alternatives ---
            "en-m": "en-IN-PrabhatNeural",      # Indian English (Male)
            "hi-m": "hi-IN-MadhurNeural",       # Hindi (Male)
            "ta-m": "ta-IN-ValluvarNeural",     # Tamil (Male)
            "te-m": "te-IN-MohanNeural",        # Telugu (Male)
            "kn-m": "kn-IN-GaganNeural",        # Kannada (Male)
            "ml-m": "ml-IN-MidhunNeural",       # Malayalam (Male)
            "bn-m": "bn-IN-BashkarNeural",      # Bengali (Male)
            "mr-m": "mr-IN-ManoharNeural",      # Marathi (Male)
            "gu-m": "gu-IN-NiranjanNeural",     # Gujarati (Male)
            "ur-m": "ur-IN-SalmanNeural",       # Urdu (Male)
        }
        return voice_map.get(language, "en-IN-NeerjaNeural")


# --- Singleton ---
_voice_service: VoiceService | None = None


def get_voice_service() -> VoiceService:
    """Returns a cached Voice service instance."""
    global _voice_service
    if _voice_service is None:
        _voice_service = VoiceService()
    return _voice_service
