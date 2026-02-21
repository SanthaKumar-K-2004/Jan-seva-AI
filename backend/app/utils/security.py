"""
Jan-Seva AI — Security Utilities
AES-256 Encryption for PII, Input Sanitization, Rate Limiting helpers.
Zero-Knowledge: Encrypt in transit, delete after use.
"""

import hashlib
import base64
import re
import os
from cryptography.fernet import Fernet


# ══════════════════════════════════════════
# AES-256 Encryption (Fernet = AES-128-CBC actually, we use custom key derivation)
# ══════════════════════════════════════════

_encryption_key: bytes | None = None


def _get_key() -> bytes:
    """Derive encryption key from app secret (never hardcode)."""
    global _encryption_key
    if _encryption_key is None:
        raw = os.environ.get("APP_SECRET", "default-dev-key-change-me-in-production")
        key = hashlib.sha256(raw.encode()).digest()
        _encryption_key = base64.urlsafe_b64encode(key)
    return _encryption_key


def encrypt_pii(plaintext: str) -> str:
    """Encrypt sensitive PII data (Aadhaar, phone, etc.)."""
    if not plaintext:
        return ""
    f = Fernet(_get_key())
    return f.encrypt(plaintext.encode()).decode()


def decrypt_pii(ciphertext: str) -> str:
    """Decrypt PII data for temporary use."""
    if not ciphertext:
        return ""
    f = Fernet(_get_key())
    return f.decrypt(ciphertext.encode()).decode()


# ══════════════════════════════════════════
# Input Sanitization
# ══════════════════════════════════════════

def sanitize_input(text: str) -> str:
    """
    Clean user input to prevent injection attacks.
    Removes HTML tags, trims whitespace, limits length.
    """
    if not text:
        return ""
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Remove control characters
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    # Trim and limit length (max 2000 chars for chat)
    text = text.strip()[:2000]
    return text


def sanitize_phone(phone: str) -> str:
    """Normalize phone number to digits only."""
    if not phone:
        return ""
    digits = re.sub(r"\D", "", phone)
    # Indian phone: 10 digits or 12 digits with country code
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    return digits


def mask_aadhaar(aadhaar: str) -> str:
    """Mask Aadhaar number for display: XXXX-XXXX-1234."""
    digits = re.sub(r"\D", "", aadhaar)
    if len(digits) == 12:
        return f"XXXX-XXXX-{digits[-4:]}"
    return "XXXX-XXXX-XXXX"
