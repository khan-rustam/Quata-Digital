"""WhatsApp/QCP view of the shared free-text PII redactor.

The free-text engine itself now lives in ``app/services/pii_text.py`` — it is
pure regex over a string, with no transport, no database and no routing, and it
is used by more than one product surface (QCP prompts and, since 2026-08-17,
the careers CV analyser). Keeping it inside this package meant every other
package had to import a QCP submodule to reuse it, which
``tests/test_whatsapp_boundaries.py`` correctly refuses: reaching past the
facade is how a caller mints or bypasses a ticket.

What stays here is the half that genuinely belongs to this package:
``safe_fact_value``, which combines the free-text sweep with
``whatsapp/redaction.py``'s key-based rules for product-supplied facts.

Everything the QCP code already imported from this module is re-exported
below, so this is a move, not a behaviour change. New callers OUTSIDE this
package should import ``app.services.pii_text`` directly.
"""

from __future__ import annotations

from app.services.pii_text import (  # noqa: F401  (re-exported for QCP callers)
    BARE_IDENTIFIER_DIGITS,
    CODE_CONTEXT_AFTER,
    CODE_CONTEXT_BEFORE,
    CODE_LONE_MAX_WORDS,
    CODE_MAX_DIGITS,
    CODE_MIN_DIGITS,
    MARK_ADDRESS,
    MARK_CARD,
    MARK_CODE,
    MARK_EMAIL,
    MARK_ID,
    MARK_PHONE,
    _redact,
    redact_customer_text,
)

from ..redaction import (
    REDACTED,
    is_maskable_key,
    is_secret_key,
    mask_identifier,
    redact,
)


def safe_fact_value(key: str, value: object) -> str:
    """One product-supplied fact value, made safe to send to the model.

    Facts come from our own products and go to the same third party as the
    customer's message, so an order fact carrying the customer's phone number
    is the identical disclosure. The *key* rules are the shared redactor's,
    unchanged and not reimplemented here:

    * a credential-shaped key (``otp_code``, ``api_key``, …) is dropped —
      ``is_secret_key``;
    * an account-shaped key (``card_number``, ``national_id``, …) keeps a
      recognisable head and tail — ``is_maskable_key`` + ``mask_identifier``,
      which is the house style for an identifier a product deliberately
      supplied;
    * everything else is bounded and control-stripped by ``redact`` and then
      swept for free-text identifiers the key never announced.

    The one free-text rule that does **not** apply here is the lone-number
    guess. A fact is a lookup result, not a customer's utterance: a product
    that answers ``order_id: 4417`` has said what the number is, so reading
    it as a possible OTP would erase the only fact the reply could be
    grounded in. The wording rule still applies — a value that says "code
    483920" is a credential whatever its key claims — as does
    ``is_secret_key``, which is what actually catches a code-shaped fact.
    """
    if is_secret_key(str(key)):
        return REDACTED
    cleaned = redact(value)
    text = cleaned if isinstance(cleaned, str) else str(cleaned)
    if is_maskable_key(str(key)):
        return mask_identifier(text)
    return _redact(text, after_auth_message=False, allow_lone_code=False)
