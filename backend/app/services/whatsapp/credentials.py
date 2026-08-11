"""Encryption at rest for QCP account secrets.

Mirrors the Fernet pattern already used for TOTP seeds in
``app/services/security_extras.py`` — the key is derived from ``SECRET_KEY``,
so a stolen database does not hand an attacker a working WhatsApp access
token. Rotating ``SECRET_KEY`` invalidates the stored credentials and the
admin must re-enter them (the same trade-off the 2FA path already makes).

Deliberately a separate module with its own key label rather than a new
function in ``security_extras``: the 2FA path is money-and-identity code and
this build does not touch it.

Nothing here ever logs, returns or formats a secret value. The only
observability it offers is *presence and length* — enough to answer "is a
token configured for this account?" without answering "what is it?".
"""
from __future__ import annotations

import base64
import hashlib
import logging
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings as env_settings


log = logging.getLogger("quata.whatsapp")

# Key label. Keeps QCP ciphertexts in their own domain, so a token can never
# be decrypted by (or confused with) the TOTP cipher.
_LABEL = b"quata-whatsapp-credentials-v1"


def _cipher() -> Fernet:
    digest = hashlib.sha256(_LABEL + env_settings.SECRET_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_wa_secret(secret: Optional[str]) -> Optional[str]:
    """Encrypt one credential for storage. Empty/None round-trips as None."""
    if secret is None:
        return None
    text = secret.strip()
    if not text:
        return None
    return _cipher().encrypt(text.encode("utf-8")).decode("ascii")


def decrypt_wa_secret(stored: Optional[str]) -> Optional[str]:
    """Return the plaintext credential, or None when it cannot be recovered.

    A ciphertext written under a previous ``SECRET_KEY`` is unreadable. That
    is reported as "not configured" (None) rather than raising — the send
    path then records a retryable ``token_not_configured`` failure the admin
    can see and fix, instead of a stack trace in a worker.
    """
    if not stored:
        return None
    try:
        return _cipher().decrypt(stored.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError, TypeError):
        log.warning("whatsapp.credential_undecryptable")
        return None


def describe_secret(stored: Optional[str]) -> dict:
    """Safe-to-log description of a credential: presence and length only.

    This is the *only* sanctioned way to say anything about a stored secret.
    It never contains any part of the value — not a prefix, not a suffix.
    """
    plain = decrypt_wa_secret(stored)
    return {"configured": bool(plain), "length": len(plain) if plain else 0}
