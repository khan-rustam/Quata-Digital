"""Payload sanitisation — runs before anything is stored or sent.

The security contract for this service is absolute: passwords, OTPs, PINs,
API keys and auth tokens must never reach Telegram, and must never reach the
``notification_events`` audit table either. So redaction happens at *ingest*,
not at render time — by the time a payload is persisted it is already safe.

Three passes:

1. **Drop** — any field whose name looks like a credential is replaced with
   ``[redacted]``. Deny-list by name, applied recursively through nested
   dicts and lists.
2. **Mask** — account-like identifiers (account/card/IBAN/wallet numbers)
   keep a recognisable head and tail; the middle becomes ``•``.
3. **Bound** — values are truncated and the payload is capped in width and
   depth so a runaway publisher can't wedge the queue with a 5 MB blob.

The deny-list matches on a *normalised* key (lowercased, separators
stripped), so ``api_key``, ``apiKey``, ``API-KEY`` and ``x_api_key`` all
collapse to the same token.
"""
from __future__ import annotations

import re
from typing import Any


REDACTED = "[redacted]"

MAX_STRING_LENGTH = 500
MAX_LIST_ITEMS = 25
MAX_DICT_KEYS = 60
MAX_DEPTH = 5


# Substrings that mark a field as a credential. Matched against the
# normalised key, so these are alphanumeric only.
_SECRET_MARKERS = (
    "password",
    "passwd",
    "passphrase",
    "pwd",
    "secret",
    "apikey",
    "accesskey",
    "privatekey",
    "publickey",
    "token",
    "bearer",
    "authorization",
    "credential",
    "otp",
    "onetimecode",
    "totp",
    "mfacode",
    "twofactorcode",
    "verificationcode",
    "resetcode",
    "pincode",
    "cvv",
    "cvc",
    "seedphrase",
    "mnemonic",
    "sessionid",
    "cookie",
    "signature",
    "salt",
    "passwordhash",
)

# Exact normalised keys that are secrets on their own but too short/generic
# to substring-match safely (e.g. "pin" would also hit "pinned_at").
_SECRET_EXACT = {"pin", "auth", "key", "hash", "code", "secret", "token", "otp"}

# Fields worth keeping but not worth printing in full.
_MASK_MARKERS = (
    "accountnumber",
    "accountno",
    "bankaccount",
    "cardnumber",
    "cardno",
    "pan",
    "iban",
    "swift",
    "walletaddress",
    "walletnumber",
    "payoutaccount",
    "nationalid",
    "idnumber",
    "passportnumber",
    "taxid",
)

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _normalise_key(key: str) -> str:
    return _NON_ALNUM.sub("", str(key).lower())


def is_secret_key(key: str) -> bool:
    norm = _normalise_key(key)
    if not norm:
        return False
    if norm in _SECRET_EXACT:
        return True
    return any(marker in norm for marker in _SECRET_MARKERS)


def is_maskable_key(key: str) -> bool:
    norm = _normalise_key(key)
    return any(marker in norm for marker in _MASK_MARKERS)


def mask_identifier(value: str, *, head: int = 2, tail: int = 4) -> str:
    """Mask the middle of an account-like identifier.

    ``1234567890123456`` → ``12••••••••••3456``. Values too short to mask
    meaningfully are replaced wholesale rather than leaked almost intact.
    """
    text = str(value).strip()
    if not text:
        return text
    if len(text) <= head + tail:
        return "•" * len(text)
    return f"{text[:head]}{'•' * (len(text) - head - tail)}{text[-tail:]}"


def _clean_string(value: str) -> str:
    """Strip control characters and bound the length."""
    text = "".join(ch for ch in str(value) if ch == "\n" or ch >= " ")
    text = text.strip()
    if len(text) > MAX_STRING_LENGTH:
        text = text[: MAX_STRING_LENGTH - 1].rstrip() + "…"
    return text


def redact(value: Any, *, _depth: int = 0) -> Any:
    """Return a sanitised deep copy of ``value``.

    Never mutates the input — publishers pass their own dicts and must not
    see them change underneath.
    """
    if _depth > MAX_DEPTH:
        return REDACTED

    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for i, (raw_key, raw_val) in enumerate(value.items()):
            if i >= MAX_DICT_KEYS:
                out["…"] = f"{len(value) - MAX_DICT_KEYS} more field(s) omitted"
                break
            key = str(raw_key)
            if is_secret_key(key):
                out[key] = REDACTED
                continue
            if is_maskable_key(key) and isinstance(raw_val, (str, int)):
                out[key] = mask_identifier(str(raw_val))
                continue
            out[key] = redact(raw_val, _depth=_depth + 1)
        return out

    if isinstance(value, (list, tuple)):
        items = list(value)[:MAX_LIST_ITEMS]
        cleaned = [redact(v, _depth=_depth + 1) for v in items]
        if len(value) > MAX_LIST_ITEMS:
            cleaned.append(f"… {len(value) - MAX_LIST_ITEMS} more item(s) omitted")
        return cleaned

    if isinstance(value, str):
        return _clean_string(value)

    if isinstance(value, (int, float, bool)) or value is None:
        return value

    # datetime, Decimal, UUID, ORM objects … — stringify then bound.
    return _clean_string(str(value))


def redact_payload(payload: dict | None) -> dict:
    """Entry point used by the dispatcher. Always returns a dict."""
    if not payload:
        return {}
    cleaned = redact(payload)
    return cleaned if isinstance(cleaned, dict) else {"value": cleaned}
