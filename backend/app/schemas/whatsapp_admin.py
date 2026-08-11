"""Pydantic IO for the QCP admin **write** surface.

``schemas/whatsapp.py`` holds the product-facing contract. This file holds
the console-facing one — the shapes behind the ``settings:manage`` routes in
``routes_admin_whatsapp.py`` that set credentials, switch accounts on,
register products and mint keys.

Three rules shape everything here, and all three are structural rather than
advisory:

**No response model carries a credential value.** Not a token, not an app
secret, not a webhook secret, not "just the first few characters". A stored
credential is described by ``CredentialStateOut`` — presence, length and a
short one-way fingerprint — and that is the only description that exists.
The credential's *name* is a **value** (``CredentialStateOut.field``), never
a response key, so no shape below can ever be flattened into a dict with a
key called ``access_token`` or ``phone_number_id``. That is what makes "no
credential key in any response" checkable by walking the JSON rather than by
reading every route.

The one exception is ``ApiKeyMintedOut.api_key``, and it is not really an
exception: that value is *generated* by the mint route, returned once, and
never stored — only its sha256 is. There is no second request that can ever
produce it again, which is the property the field name and ``shown_once``
advertise to the console.

**A fingerprint answers one question.** ``sha256(value)[:12]`` says "is this
the same secret as before?" and nothing else. It is what makes the audit
trail's *old → new* record possible without the audit trail holding a
secret, and it is why an operator can confirm the token they pasted is the
token that is stored without either of them printing it.

**An unset Meta identifier is a security state.** ``AccountAdminOut.security``
carries typed ``SecurityWarningOut`` rows rather than leaving the console to
infer severity from an empty field. An empty ``phone_number_id`` is not an
incomplete form: webhook cross-number attribution is skipped while it is the
seeded empty string, and both numbers normally share one app secret, so a
QUATA envelope would verify at the Quata Verify webhook. That is a
``critical``, and the console is given it as one.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


PURPOSES = ("authentication", "engagement")

# Meta identifiers are numeric strings; the display phone is E.164. Validated
# here so a paste with a stray quote or a whole URL in it is a 422 the
# operator can see, rather than a stored value that fails at Meta hours later.
_META_ID = r"^\d{5,40}$"
_E164 = r"^\+[1-9]\d{5,22}$"
_API_VERSION = r"^v\d{1,3}\.\d{1,3}$"
_SLUG = r"^[a-z][a-z0-9_]{2,39}$"


# ---------------------------------------------------------------------------
# Shared output pieces
# ---------------------------------------------------------------------------

class CredentialStateOut(BaseModel):
    """Everything the console may know about one stored credential.

    ``field`` is the credential's name carried as a *value*, so this model
    can be listed without any response ever growing a key named after a
    secret. ``fingerprint`` is ``sha256(plaintext)[:12]`` — enough to answer
    "did this change?" and "is this the value I pasted?", and nothing else.
    """

    field: str
    label: str
    configured: bool
    length: int = 0
    fingerprint: Optional[str] = None
    # False for a credential an account can be switched on without.
    required_to_enable: bool = True


class SecurityWarningOut(BaseModel):
    """A configuration state that is a security posture, not a blank field.

    ``severity`` exists so the console cannot render "phone number id is
    empty" with the same weight as "display name not set". A ``critical``
    means the platform is currently *less safe* than it looks.
    """

    code: str
    severity: Literal["critical", "warning"]
    message: str


class AccountAdminOut(BaseModel):
    """One WhatsApp number as the write surface reports it.

    Deliberately a different shape from ``routes_admin_whatsapp._account_out``
    (the read surface the console's TypeScript is pinned against): this one
    answers "what is stopping me switching this on, and what is unsafe about
    it right now", which the read shape does not.
    """

    slug: str
    name: str
    purpose: str
    display_phone: Optional[str] = None
    api_version: str
    is_active: bool
    health: str
    quality_rating: Optional[str] = None
    messaging_limit: Optional[str] = None
    last_checked_at: Optional[datetime] = None
    last_error: Optional[str] = None
    # Could it address Meta at all? Says nothing about whether it is on.
    configured: bool
    # Every credential and Meta identifier, described, never disclosed.
    credentials: list[CredentialStateOut]
    # Field names still missing before ``enable`` will be accepted.
    blocking: list[str] = Field(default_factory=list)
    security: list[SecurityWarningOut] = Field(default_factory=list)
    # False while ``phone_number_id`` is unset: the webhook cannot then tell
    # an envelope for this number from an envelope for the other one.
    webhook_cross_number_attribution: bool = False


class ProductAdminOut(BaseModel):
    """One registered product as the write surface reports it."""

    slug: str
    name: str
    description: Optional[str] = None
    is_enabled: bool
    allowed_purposes: list[str]
    default_locale: str
    rate_limit_per_minute: int
    # An empty ``api_key_hash`` is an explicit denial at the gateway: no
    # sha256 hex digest equals "", so a keyless product cannot authenticate.
    has_api_key: bool
    api_key_prefix: Optional[str] = None
    api_key_fingerprint: Optional[str] = None
    may_reach_authentication: bool
    last_seen_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Accounts — input
# ---------------------------------------------------------------------------

class AccountCredentialsIn(BaseModel):
    """A partial credential update. Only the fields sent are written.

    Every field is optional so an operator can rotate one token without
    re-pasting the other five, and ``extra="forbid"`` means a typo'd field
    name is a 422 rather than a silently ignored write that leaves the
    console showing a change that never happened.
    """

    model_config = ConfigDict(extra="forbid")

    access_token: Optional[str] = Field(default=None, min_length=8, max_length=1024)
    app_secret: Optional[str] = Field(default=None, min_length=8, max_length=512)
    webhook_verify_token: Optional[str] = Field(default=None, min_length=8, max_length=512)
    phone_number_id: Optional[str] = Field(default=None, pattern=_META_ID)
    waba_id: Optional[str] = Field(default=None, pattern=_META_ID)
    display_phone: Optional[str] = Field(default=None, pattern=_E164)
    api_version: Optional[str] = Field(default=None, pattern=_API_VERSION)

    @model_validator(mode="after")
    def _at_least_one(self) -> "AccountCredentialsIn":
        if not self.model_fields_set:
            raise ValueError("Send at least one credential field.")
        return self


class AccountEnableIn(BaseModel):
    """Switching a number on is what lets QCP address Meta at all.

    It is the most consequential action in this system, so it is the only one
    that asks the operator to type the account's own slug back and say why.
    Both land in the audit row: ``justification`` is the field that makes
    "who turned Quata Verify on, and what for" answerable six months later.
    """

    model_config = ConfigDict(extra="forbid")

    confirm_slug: str = Field(..., min_length=1, max_length=40)
    justification: str = Field(..., min_length=8, max_length=500)


class ConnectionTestOut(BaseModel):
    """Result of asking Meta whether the number is healthy.

    ``sent_message`` is pinned ``False`` in the contract, not merely absent:
    a "test" that could put a message on a real customer's phone is not a
    test, and the console should be able to say so on the button.
    """

    account: AccountAdminOut
    ok: bool
    health: str
    quality_rating: Optional[str] = None
    messaging_limit: Optional[str] = None
    verified_name: Optional[str] = None
    error: Optional[str] = None
    sent_message: Literal[False] = False


# ---------------------------------------------------------------------------
# Products — input
# ---------------------------------------------------------------------------

class ProductRegisterIn(BaseModel):
    """Register a product in the plugin registry.

    Note what is *not* here: ``allowed_purposes``, ``is_enabled`` and any key
    material. A newly registered product is engagement-only, disabled and
    keyless — the same shape the seeder produces — so registering one can
    never be the act that opens an authentication path or starts traffic.
    """

    model_config = ConfigDict(extra="forbid")

    slug: str = Field(..., pattern=_SLUG)
    name: str = Field(..., min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)
    default_locale: str = Field(default="en", min_length=2, max_length=10)
    rate_limit_per_minute: int = Field(default=600, ge=1, le=100_000)


class ProductPurposesIn(BaseModel):
    """Set the ceiling of account purposes a product may ever reach.

    This route may **remove** ``authentication`` but never add it. Adding it
    is a separate, justified, separately-audited action
    (``POST .../purposes/authentication``) precisely so that re-opening a
    WhatsApp auth path for a product that gave one up — QuataPay moved to
    email OTP on 2026-06-03 — cannot happen as one checkbox among many in a
    form somebody was editing for another reason.
    """

    model_config = ConfigDict(extra="forbid")

    purposes: list[Literal["authentication", "engagement"]] = Field(
        ..., min_length=1, max_length=2
    )

    @field_validator("purposes")
    @classmethod
    def _unique(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("Duplicate purpose.")
        return value


class ProductAuthenticationGrantIn(BaseModel):
    """Grant a product the right to reach the Quata Verify number.

    ``justification`` is mandatory and stored on the audit row. This grant is
    the one that puts a product's traffic next to the fleet's OTP path, and
    the audit answer "because <blank>" is worth nothing.
    """

    model_config = ConfigDict(extra="forbid")

    justification: str = Field(..., min_length=8, max_length=500)


class ApiKeyMintedOut(BaseModel):
    """The one response in QCP that carries a secret value, exactly once.

    The key is generated here, handed back here, and never stored: only
    ``sha256(key)`` and a non-reversible display prefix reach the database,
    so no later request — by this operator or anyone else — can produce it
    again. ``shown_once`` is in the contract so the console renders the
    copy-it-now affordance instead of assuming it can re-read the value.
    """

    product: ProductAdminOut
    api_key: str
    prefix: str
    fingerprint: str
    shown_once: Literal[True] = True
    notice: str = (
        "This key is shown once and is not stored. Copy it now; "
        "if it is lost, rotate the key rather than trying to recover it."
    )


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

class ConversationReassignIn(BaseModel):
    """Hand an unattributed inbound conversation to a product.

    The attribution engine deliberately gives an ambiguous customer reply to
    **nobody** and raises ``conversation.inbound_unattributed``. This is the
    human's side of that decision, and it is the only path in QCP that sets
    ``product_id`` on a thread that ingest left blank.
    """

    model_config = ConfigDict(extra="forbid")

    product: str = Field(..., pattern=_SLUG)
    reason: Optional[str] = Field(default=None, max_length=300)


class ConversationReassignOut(BaseModel):
    conversation_id: int
    product: str
    account: str
    account_purpose: str
    # Inbound rows that ingest left unattributed and this hand-over claimed.
    # Messages already carrying another product's id are never moved.
    messages_attributed: int
    state: str
