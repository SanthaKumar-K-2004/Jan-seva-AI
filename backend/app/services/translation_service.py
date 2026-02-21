"""
Jan-Seva AI — Translation Service (AI4Bharat IndicTrans2 Powered)
Uses AI4Bharat's IndicTrans2 (free, unlimited, purpose-built for Indian languages).
Lazy-loads the model to avoid startup overhead, with Google Translate as fallback.
"""

import json
import os
from app.utils.logger import logger


# ═══════════════════════════════════════════════════════════
# BCP-47 / ISO 639-1 → Flores-200 language code mapping
# IndicTrans2 uses Flores-200 codes internally
# ═══════════════════════════════════════════════════════════
LANG_TO_FLORES = {
    "en": "eng_Latn",
    "hi": "hin_Deva",
    "ta": "tam_Taml",
    "te": "tel_Telu",
    "kn": "kan_Knda",
    "ml": "mal_Mlym",
    "bn": "ben_Beng",
    "mr": "mar_Deva",
    "gu": "guj_Gujr",
    "pa": "pan_Guru",
    "or": "ory_Orya",
    "as": "asm_Beng",
    "ur": "urd_Arab",
    "sa": "san_Deva",
    "ne": "npi_Deva",
    "sd": "snd_Arab",
    "ks": "kas_Arab",
    "doi": "doi_Deva",
    "kok": "gom_Deva",
    "mni": "mni_Beng",
    "sat": "sat_Olck",
    "mai": "mai_Deva",
    "bh": "bho_Deva",
}

INDIAN_LANGUAGES = {
    "en": "english",
    "hi": "hindi",
    "ta": "tamil",
    "te": "telugu",
    "kn": "kannada",
    "ml": "malayalam",
    "bn": "bengali",
    "mr": "marathi",
    "gu": "gujarati",
    "pa": "punjabi",
    "or": "odia",
    "as": "assamese",
    "ur": "urdu",
    "sa": "sanskrit",
    "ne": "nepali",
    "sd": "sindhi",
    "ks": "kashmiri",
    "doi": "dogri",
    "kok": "konkani",
    "mni": "manipuri",
    "sat": "santali",
    "mai": "maithili",
    "bh": "bhojpuri",
}


class IndicTransEngine:
    """
    AI4Bharat IndicTrans2 engine — lazy-loaded for zero startup cost.
    Uses the distilled 200M model for fast CPU inference.
    """

    def __init__(self):
        self._en_indic_model = None
        self._en_indic_tokenizer = None
        self._indic_en_model = None
        self._indic_en_tokenizer = None
        self._processor = None
        self._available = None  # None = not checked, True/False = checked

    def is_available(self) -> bool:
        """Check if IndicTrans2 dependencies are installed."""
        if self._available is None:
            try:
                import torch  # noqa: F401
                from transformers import AutoModelForSeq2SeqLM, AutoTokenizer  # noqa: F401
                from IndicTransToolkit import IndicProcessor  # noqa: F401
                self._available = True
            except (ImportError, OSError):
                self._available = False
                logger.info("ℹ️ IndicTrans2 not installed — using Google Translate fallback")
        return self._available

    def _load_en_indic(self):
        """Load English→Indic model (lazy, ~800MB download first time)."""
        if self._en_indic_model is None:
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
            import torch

            model_name = "ai4bharat/indictrans2-en-indic-dist-200M"
            logger.info(f"📦 Loading IndicTrans2 En→Indic: {model_name}...")

            self._en_indic_tokenizer = AutoTokenizer.from_pretrained(
                model_name, trust_remote_code=True
            )
            self._en_indic_model = AutoModelForSeq2SeqLM.from_pretrained(
                model_name, trust_remote_code=True
            )
            # Use CPU by default — GPU if available
            device = "cuda" if torch.cuda.is_available() else "cpu"
            self._en_indic_model = self._en_indic_model.to(device)
            self._en_indic_model.eval()
            logger.info(f"✅ IndicTrans2 En→Indic loaded on {device}")

        return self._en_indic_model, self._en_indic_tokenizer

    def _load_indic_en(self):
        """Load Indic→English model (lazy, ~800MB download first time)."""
        if self._indic_en_model is None:
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
            import torch

            model_name = "ai4bharat/indictrans2-indic-en-dist-200M"
            logger.info(f"📦 Loading IndicTrans2 Indic→En: {model_name}...")

            self._indic_en_tokenizer = AutoTokenizer.from_pretrained(
                model_name, trust_remote_code=True
            )
            self._indic_en_model = AutoModelForSeq2SeqLM.from_pretrained(
                model_name, trust_remote_code=True
            )
            device = "cuda" if torch.cuda.is_available() else "cpu"
            self._indic_en_model = self._indic_en_model.to(device)
            self._indic_en_model.eval()
            logger.info(f"✅ IndicTrans2 Indic→En loaded on {device}")

        return self._indic_en_model, self._indic_en_tokenizer

    def _get_processor(self):
        """Get IndicProcessor for pre/post processing."""
        if self._processor is None:
            from IndicTransToolkit import IndicProcessor
            self._processor = IndicProcessor(inference=True)
        return self._processor

    def translate(self, text: str, src_lang: str, tgt_lang: str) -> str:
        """Translate text using IndicTrans2."""
        import torch

        src_flores = LANG_TO_FLORES.get(src_lang)
        tgt_flores = LANG_TO_FLORES.get(tgt_lang)

        if not src_flores or not tgt_flores:
            raise ValueError(f"Unsupported language pair: {src_lang} → {tgt_lang}")

        ip = self._get_processor()

        # Determine direction and load appropriate model
        if src_lang == "en":
            model, tokenizer = self._load_en_indic()
        else:
            model, tokenizer = self._load_indic_en()

        # Preprocess
        batch = ip.preprocess_batch([text], src_lang=src_flores, tgt_lang=tgt_flores)

        # Tokenize
        device = next(model.parameters()).device
        inputs = tokenizer(
            batch, truncation=True, padding="longest",
            max_length=256, return_tensors="pt"
        ).to(device)

        # Generate
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                num_beams=5,
                num_return_sequences=1,
                max_length=256,
            )

        # Decode
        with tokenizer.as_target_tokenizer():
            decoded = tokenizer.batch_decode(outputs, skip_special_tokens=True)

        # Postprocess
        result = ip.postprocess_batch(decoded, lang=tgt_flores)
        return result[0] if result else text

    def translate_batch(self, texts: list[str], src_lang: str, tgt_lang: str) -> list[str]:
        """Translate a batch of texts using IndicTrans2."""
        import torch

        src_flores = LANG_TO_FLORES.get(src_lang)
        tgt_flores = LANG_TO_FLORES.get(tgt_lang)

        if not src_flores or not tgt_flores:
            return texts

        ip = self._get_processor()

        if src_lang == "en":
            model, tokenizer = self._load_en_indic()
        else:
            model, tokenizer = self._load_indic_en()

        # Preprocess
        batch = ip.preprocess_batch(texts, src_lang=src_flores, tgt_lang=tgt_flores)

        device = next(model.parameters()).device
        inputs = tokenizer(
            batch, truncation=True, padding="longest",
            max_length=256, return_tensors="pt"
        ).to(device)

        with torch.no_grad():
            outputs = model.generate(
                **inputs, num_beams=5, num_return_sequences=1, max_length=256,
            )

        with tokenizer.as_target_tokenizer():
            decoded = tokenizer.batch_decode(outputs, skip_special_tokens=True)

        result = ip.postprocess_batch(decoded, lang=tgt_flores)
        return result


class TranslationService:
    """
    Translation with AI4Bharat IndicTrans2 (primary) + Google Translate (fallback).
    Applies glossary post-processing to fix government/legal terminology.
    """

    def __init__(self):
        # Load glossary
        glossary_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "data", "glossary.json"
        )
        self._glossary = {}
        if os.path.exists(glossary_path):
            with open(glossary_path, "r", encoding="utf-8") as f:
                self._glossary = json.load(f)
            logger.info(
                f"📖 Glossary loaded: {sum(len(v) for v in self._glossary.values())} "
                f"terms across {len(self._glossary)} languages"
            )

        # IndicTrans2 engine (lazy-loaded)
        self._indic = IndicTransEngine()

    def translate(self, text: str, source: str = "en", target: str = "hi") -> str:
        """
        Translate text:
        1. Try IndicTrans2 (best for Indian languages, free, unlimited)
        2. Fallback to Google Translate if IndicTrans2 unavailable
        3. Apply glossary post-processing
        """
        if source == target:
            return text

        translated = None

        # --- Strategy 1: IndicTrans2 (AI4Bharat) ---
        if self._indic.is_available():
            try:
                translated = self._indic.translate(text, source, target)
                logger.debug(f"✅ IndicTrans2: {source}→{target}")
            except Exception as e:
                logger.warning(f"⚠️ IndicTrans2 failed: {e}")

        # --- Strategy 2: Google Translate fallback ---
        if translated is None:
            try:
                from deep_translator import GoogleTranslator
                src_code = self._normalize_google_code(source)
                tgt_code = self._normalize_google_code(target)
                translated = GoogleTranslator(source=src_code, target=tgt_code).translate(text)
                if not translated:
                    translated = text
                logger.debug(f"✅ Google Translate fallback: {source}→{target}")
            except Exception as e:
                logger.warning(f"⚠️ Google Translate also failed: {e}")
                return text

        # --- Step 3: Apply glossary corrections ---
        lang_glossary = self._glossary.get(target, {})
        for wrong_term, correct_term in lang_glossary.items():
            translated = translated.replace(wrong_term, correct_term)

        return translated

    def translate_batch(self, texts: list[str], source: str = "en", target: str = "hi") -> list[str]:
        """Translate a batch of texts."""
        if source == target:
            return texts

        # Try IndicTrans2 batch (much faster)
        if self._indic.is_available():
            try:
                results = self._indic.translate_batch(texts, source, target)
                # Apply glossary to each
                lang_glossary = self._glossary.get(target, {})
                if lang_glossary:
                    for i, text in enumerate(results):
                        for wrong, correct in lang_glossary.items():
                            results[i] = results[i].replace(wrong, correct)
                return results
            except Exception as e:
                logger.warning(f"⚠️ IndicTrans2 batch failed: {e}")

        # Fallback: individual Google Translate
        return [self.translate(t, source, target) for t in texts]

    def detect_language(self, text: str) -> str:
        """Detect the language of input text."""
        try:
            from langdetect import detect
            detected = detect(text)
            return detected if detected in INDIAN_LANGUAGES else "en"
        except Exception:
            return "en"

    def _normalize_google_code(self, code: str) -> str:
        """Normalize language codes for Google Translate compatibility."""
        code_map = {
            "or": "or",
            "as": "as",
            "doi": "doi",
            "kok": "gom",
            "mni": "mni-Mtei",
            "sat": "sat",
            "mai": "mai",
            "bh": "bho",
        }
        return code_map.get(code, code)

    @staticmethod
    def get_supported_languages() -> dict:
        """Return all supported Indian languages."""
        return INDIAN_LANGUAGES.copy()


# --- Singleton ---
_translation_service: TranslationService | None = None


def get_translation_service() -> TranslationService:
    global _translation_service
    if _translation_service is None:
        _translation_service = TranslationService()
    return _translation_service
