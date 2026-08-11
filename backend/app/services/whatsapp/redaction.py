"""Sanitisation for everything QCP persists.

Ported from ``services/notifications/redaction.py`` — same deny-list, same
contract: redaction happens at *ingest*, so by the time a row is written it
is already safe.

QCP adds one rule the notification service does not need. WhatsApp
authentication templates carry the OTP as a template *variable*, and the
message row must stay reconstructible enough to debug ("did we send the
right code?") without ever storing the code. So a secret-looking variable
becomes ``sha256:<8 hex>`` rather than ``[redacted]`` — the same value
hashes the same way, so a support engineer can compare a customer's quoted
code against the row without the row ever holding it.

**The name of a variable is not evidence of anything.** Meta's authentication
templates are positional — the placeholder is ``{{1}}``, so the name that
reaches storage is ``"1"``, and an operator is equally free to call it
``verification``, ``value`` or ``number``. None of those are on the deny-list
and none ever will be reliably. So the deciding signal is the resolved
template's **category**: if it is ``authentication``, every variable is
digested unconditionally, whatever it is called. The name-based deny-list
stays on as an additional trigger for the other categories, where a
utility template may still carry something sensitive.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Sequence

from app.services.notifications.redaction import (  # noqa: F401 — re-export
    REDACTED,
    is_maskable_key,
    is_secret_key,
    mask_identifier,
    redact,
)


CATEGORY_AUTHENTICATION = "authentication"

# The two *markers* ``redact_variables`` writes in place of a real value. Both
# are literal markers, not content patterns: a template variable cannot
# legitimately be either of them.
_DIGEST_PREFIX = "sha256:"


# ---------------------------------------------------------------------------
# Belt and braces: a code that reached a non-authentication template
# ---------------------------------------------------------------------------

# Category is the primary rule and the deny-list is the second, but neither
# forbids an operator wiring a verification code onto a *utility* template on
# the marketing number — and the deny-list does not carry ``auth_code`` or
# ``passcode``. So a third, deliberately narrow rule: a name that reads like a
# secret **and** a value that is a bare short numeric code is digested in every
# category. Both halves are required, which is what stops it swallowing the
# order ids and ETAs the admin console exists to show.
#
# The name it is matched against is the *declared* one where the row was
# renamed positionally before storage (``declared_names``) — matching only
# the stored ordinal is why this rule fired on nothing real.
_SECRETISH_SUBSTRINGS = (
    "code",
    "otp",
    "token",
    "secret",
    "password",
    "passphrase",
    "verification",
    "verify",
)
# Short ones only match at the head, so ``shipping`` is not read as ``pin``.
_SECRETISH_PREFIXES = ("pin", "auth", "mfa", "twofactor", "2fa")

# …and the names that carry "code" while being ordinary engagement copy.
_SECRETISH_ALLOWED = (
    "postcode",
    "postalcode",
    "zipcode",
    "areacode",
    "dialcode",
    "countrycode",
    "currencycode",
    "languagecode",
    "barcode",
    "qrcode",
    "promocode",
    "couponcode",
    "vouchercode",
    "discountcode",
    "referralcode",
    "trackingcode",
    "ordercode",
    "storecode",
    "branchcode",
    "invoicecode",
)

_NON_ALNUM_NAME = re.compile(r"[^a-z0-9]+")
# 4–10 digits, optionally grouped by spaces or hyphens: "483920", "483 920".
_BARE_CODE = re.compile(r"^\d[\d \-]{2,12}\d$")
# ``_record_suppressed`` and the arity-mismatch branch of
# ``_variables_for_storage`` both name variables ``"1"``, ``"2"``, … — that
# is what ``declared_names`` is realigned against.
_POSITIONAL_NAME = re.compile(r"^\d+$")


def _looks_like_secret_name(key: str) -> bool:
    norm = _NON_ALNUM_NAME.sub("", str(key).lower())
    if not norm or any(allowed in norm for allowed in _SECRETISH_ALLOWED):
        return False
    if any(marker in norm for marker in _SECRETISH_SUBSTRINGS):
        return True
    return norm.startswith(_SECRETISH_PREFIXES)


def looks_like_authentication_intent(intent: str | None) -> bool:
    """Whether the *product* asked for something a login code belongs in.

    The template's ``category`` is operator-typed data — the defect that
    started all of this — and Meta may re-classify a template underneath it.
    The intent is not: it is what the calling product passed to ``send()``,
    which is the one description of the message nobody in the admin console
    edits.

    Same vocabulary as the variable-name rule, including its allow-list, so a
    ``promo_code`` or ``tracking_code`` intent is not read as
    authentication. Deliberately no value test: an intent applies to the
    whole message, and ``login_otp`` means every variable on it is part of
    the code, exactly as it does for ``category=authentication``.
    """
    return bool(intent) and _looks_like_secret_name(intent)


def _looks_like_bare_code(value: object) -> bool:
    text = str(value).strip()
    if not _BARE_CODE.match(text):
        return False
    return 4 <= len(re.sub(r"[ \-]", "", text)) <= 10


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:8]


def is_redacted_value(value: Any) -> bool:
    """True when a stored value is one of the markers redaction writes.

    Used by the delivery path to decide whether a row can be re-rendered.
    Recognition is by *marker*: a ``sha256:`` digest, or the shared redactor's
    ``[redacted]`` for a nested credential. Recognising only the first was the
    original bug.

    It is **not** by content. This used to also call any value containing
    ``•`` a masked identifier, which is a sniff on an ordinary printable
    character: "Chez Paul • Douala" is a normal restaurant name in the city
    this platform serves, and such a variable was refused as
    ``payload_not_recoverable`` with nothing reported to the product. The
    sniff had no true positives to pay for that — ``mask_identifier`` builds
    its mask from ``•``, but ``redact`` only masks maskable *keys of a nested
    dict*, and a template variable is a scalar, so ``redact_variables`` never
    emits a mask at all.
    """
    if not isinstance(value, str):
        return False
    return value.startswith(_DIGEST_PREFIX) or value == REDACTED


def _hinted_names(variables: dict, declared_names: Sequence[str] | None) -> dict:
    """Map each positional key back to the name the template declared for it.

    Storage renames variables to ordinals **before** redaction runs, so by the
    time a name-based rule looks at ``"1"`` the operator's own
    ``auth_code`` is gone. It is not lost, though — the template still
    declares it, and the caller that did the renaming knows the order. This
    puts the two back together.

    Alignment is all-or-nothing. A ``declared_names`` of a different length
    than the row cannot be aligned, and guessing an alignment would digest an
    arbitrary variable — which is the "digest everything" answer this must
    not be. Keys that are not ordinals already carry the declared name.
    """
    if not declared_names or len(declared_names) != len(variables):
        return {}
    return {
        key: str(declared_names[int(key) - 1])
        for key in variables
        if _POSITIONAL_NAME.match(str(key))
        and 1 <= int(key) <= len(declared_names)
    }


def redact_variables(
    variables: dict | None,
    *,
    template_category: str | None = None,
    intent: str | None = None,
    declared_names: Sequence[str] | None = None,
) -> dict:
    """Redact template variables for storage.

    ``intent`` and ``declared_names`` exist because the name-based rules below
    were, on every row QCP actually holds, matching against an ordinal.
    ``_record_suppressed`` names variables ``"1"``, ``"2"``, … before calling
    this, and QCP ships dormant, so *suppressed* is the shape of the whole
    backlog. A code an operator wired onto a utility template therefore
    reached storage in clear no matter what it had been called.

    * ``declared_names`` is the template's own placeholder list, positionally
      aligned with the values, so the name rule is applied to the name the
      operator chose rather than to the ordinal that replaced it.
    * ``intent`` is what the *product* asked for. It is the one signal on the
      message that no admin form edits, so it still says ``login_otp`` when
      ``category`` says ``utility`` — whether by operator error or because
      Meta re-classified the template. An authentication-shaped intent
      digests every variable, like ``category=authentication`` does.

    Neither is a blanket digest, and that is the point: an
    ``order_dispatched`` intent whose placeholders are ``order_number`` and
    ``eta`` keeps both readable, which is the entire reason redaction keys on
    category instead of digesting everything.

    ``template_category`` is the resolved template's Meta category. When it is
    ``authentication`` **every** variable is digested, because on an
    authentication template every variable is, by construction, part of the
    code the user is about to type. Positional names (``"1"``) and
    innocent-looking ones (``verification``, ``value``, ``number``) are the
    normal case there, and no deny-list catches them.

    Otherwise the name-based rule applies: secret-ish names (``code``,
    ``otp``, ``pin``, ``token``, …) are replaced by a short digest of the
    value; everything else goes through the shared redactor and stays
    readable, which is what makes the admin console able to answer "what did
    we send this customer?".

    On top of that, and in *every* category, a name that merely reads like a
    secret is digested when its value is also a bare short numeric code.
    Nothing forbids an operator wiring a verification code onto a utility
    template on the marketing number, and the deny-list carries neither
    ``auth_code`` nor ``passcode``. Requiring both halves is what keeps order
    ids, ETAs and promo codes readable.

    The digest is stable — the same value always hashes the same way — so
    support can compare a quoted code against the row without the row ever
    holding it.
    """
    if not variables:
        return {}
    force = str(
        template_category or ""
    ).strip().lower() == CATEGORY_AUTHENTICATION or looks_like_authentication_intent(
        intent
    )
    hints = _hinted_names(variables, declared_names)
    out: dict = {}
    for key, value in variables.items():
        name = str(key)
        # The stored name and, when the row was renamed positionally, the
        # name the template declared for that position. Either may trigger.
        candidates = {name, hints.get(key, name)}
        if (
            force
            or any(is_secret_key(c) for c in candidates)
            or (
                any(_looks_like_secret_name(c) for c in candidates)
                and _looks_like_bare_code(value)
            )
        ):
            out[name] = _digest(value)
            continue
        cleaned = redact(value)
        out[name] = cleaned
    return out


def redact_body(body: str | None) -> str | None:
    """Bound + strip a rendered message body before it is stored."""
    if body is None:
        return None
    cleaned = redact(body)
    return cleaned if isinstance(cleaned, str) else str(cleaned)


def redact_details(details: dict | None) -> dict:
    """Audit-log ``details``. Always a dict, never a credential."""
    if not details:
        return {}
    cleaned = redact(details)
    return cleaned if isinstance(cleaned, dict) else {"value": cleaned}
