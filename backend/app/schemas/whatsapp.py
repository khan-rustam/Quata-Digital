"""Pydantic IO for QCP.

This file holds the **product-facing** contract — what QuataPay, QuataFood,
Abaqwa and friends send and receive. (Admin console schemas live alongside
it; see ``routes_admin_whatsapp.py``.)

One rule shapes every model here: **a product cannot name an account.**
``MessageSendIn`` forbids extra fields, so a caller that tries to pass
``account_slug``, ``purpose``, ``phone_number_id`` or ``template`` is
rejected with 422 rather than having the field quietly ignored. The account
is chosen server-side by ``routing.resolve_route`` from the routing rules,
and there is no request field that participates in that choice.

Nothing here ever carries a credential. Account rows are not exposed to
products at all — not the slug, not the display phone, not the phone number
id — so a product cannot even learn which number carried its message.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------

class MessageSendIn(BaseModel):
    """One outbound message request from a product.

    ``variables`` is the **ordered list of placeholder values**, matching the
    order of the template's declared placeholder names. Arity is checked
    against the approved template; a mismatch is refused rather than padded.
    Values are hashed or redacted before storage — an OTP is never persisted
    in clear.
    """

    model_config = ConfigDict(extra="forbid")

    intent: str = Field(..., min_length=1, max_length=80)
    to: str = Field(..., min_length=6, max_length=24)
    variables: list[str] = Field(default_factory=list, max_length=32)
    locale: Optional[str] = Field(default=None, max_length=10)
    kind: Literal["template", "text"] = "template"
    # Free-form (kind != "template") must name the thread it replies to, so
    # the 24h service window can be checked and ownership verified.
    conversation_id: Optional[int] = None
    body: Optional[str] = Field(default=None, max_length=4096)
    # Business reference. Also pins the idempotency bucket, so two OTPs for
    # the same reference are one message and a genuine resend is a new one.
    reference: Optional[str] = Field(default=None, max_length=160)


class MessageAcceptedOut(BaseModel):
    message_uid: str
    status: str
    duplicate: bool = False
    # Stable denial code when status == "suppressed".
    reason: Optional[str] = None


class MessageOut(BaseModel):
    message_uid: str
    status: str
    direction: str
    kind: str
    intent: Optional[str] = None
    to: Optional[str] = None
    conversation_id: Optional[int] = None
    attempts: int = 0
    error_code: Optional[str] = None
    last_error: Optional[str] = None
    suppressed_reason: Optional[str] = None
    created_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

class ConversationOut(BaseModel):
    id: int
    phone_e164: str
    display_name: Optional[str] = None
    state: str
    assignee_id: Optional[int] = None
    unread_count: int = 0
    locale: Optional[str] = None
    last_inbound_at: Optional[datetime] = None
    last_outbound_at: Optional[datetime] = None
    service_window_expires_at: Optional[datetime] = None
    service_window_open: bool = False
    created_at: Optional[datetime] = None


class ConversationAssignIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assignee_id: int


class ConversationHistoryOut(BaseModel):
    conversation_id: int
    messages: list[MessageOut]
    next_before_id: Optional[int] = None


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class ProductHealthOut(BaseModel):
    """What a product is allowed to know about QCP's readiness.

    Deliberately says *whether* a purpose is reachable, never which number
    backs it.
    """

    ok: bool
    product: str
    enabled: bool
    delivery_enabled: bool
    allowed_purposes: list[str]
    purpose_available: dict[str, bool]
    active_intents: list[str]
