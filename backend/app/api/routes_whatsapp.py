"""QCP — the product-facing API gateway.

This is the surface QuataPay, QuataFood, Abaqwa, QuataTrade and every future
QUATA product call. It is deliberately narrow, and two properties are
load-bearing:

**A product cannot choose the account.** There is no request field — header,
path, query or body — through which a caller can name a WhatsApp number, a
phone number id, a WABA, an account slug or a purpose. ``MessageSendIn``
sets ``extra="forbid"``, so an attempt to pass one is a 422 rather than a
silently ignored field. The number is chosen server-side by
``routing.resolve_route`` from ``whatsapp_routing_rules``, and the three
category-scoped endpoints below (``/authentication``, ``/utility``,
``/marketing``) only ever *narrow* an already-resolved route — they cannot
widen or redirect one. A QuataFood promotion cannot leave Quata Verify even
from a caller that knows every internal id.

**A product can only act on its own conversations.** Two tiers, because
``(account_id, wa_contact_id)`` is unique and four products on the shared
engagement number land on *one* row per customer:

* *reading* a thread (``_readable`` → ``conversations.for_product``) is
  allowed to the owner **or** to a product that already has a message in it,
  so deciding who gets the next inbound never retracts a message a product
  was already given. What it reads is scoped again on
  ``whatsapp_messages.product_id``, so a shared row never shares a message;
* *changing* one (``_owned`` → ``conversations.owned_by_product``) — the
  state verbs, and naming a ``conversation_id`` on a send — requires
  ownership. ``state``, ``unread_count`` and ``assignee_id`` are shared
  columns, and participation costs one utility send to a guessable phone
  number; that must not buy the power to close another product's live
  customer thread, take its human agent off it, or put free-form prose on
  its customer's phone through the service window that customer opened.

Either way the answer is a 404, not a 403, so the endpoints cannot be used
to probe for the existence of another product's thread.

Authentication is ``X-QCP-Product`` + ``X-QCP-Key`` (compared against
``whatsapp_products.api_key_hash`` in constant time), plus an
``X-QCP-Signature``/``X-QCP-Timestamp`` HMAC when signatures are required.
Structurally this is ``_authenticate_platform`` from
``routes_notifications.py:71-105``, with one difference: QCP stores only the
*hash* of a product key, never the key, so the request HMAC is keyed with
that hash — which the product can derive from the key it holds and QCP can
recompute without ever storing the secret.

The Meta-facing webhook half of this router lives alongside these routes.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip
from app.core.config import settings as env_settings
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models import (
    WhatsAppAccount,
    WhatsAppMessage,
    WhatsAppProduct,
    WhatsAppRoutingRule,
    WhatsAppTemplate,
)
from app.schemas.whatsapp import (
    ConversationAssignIn,
    ConversationHistoryOut,
    ConversationOut,
    MessageAcceptedOut,
    MessageOut,
    MessageSendIn,
    ProductHealthOut,
)
from app.services.whatsapp import audit, conversations, routing, settings_store, webhooks


log = logging.getLogger("quata.whatsapp")

router = APIRouter(tags=["whatsapp"])


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# The path whose budget must survive everything else QCP does.
AUTH_SEND_PATH = "/whatsapp/messages/authentication"


# The bucket a QCP caller is charged against.
#
# ``_key_user_or_ip`` (the app-wide default) falls back to ``ip:<addr>`` for
# anything without a bearer token, and QCP callers never carry one. QuataPay,
# QuataFood and Abaqwa can egress through a single address, so one product's
# burst would rate-limit another product's OTPs. Keyed on the claimed product
# instead — and on the address too, because the product header is not
# authenticated at this point: without the address, anyone could name
# ``quatapay`` and burn the real QuataPay's bucket. The cost of including it
# is that a product egressing from several addresses gets a bucket per
# address, which is the lenient direction and the right one for OTP traffic.
#
# Two things that bucket got wrong, and both end at the same place — a
# QuataFood login OTP that 429s. QuataFood login, payment-PIN reset and
# phone-change verification have no email fallback, so that is a lockout:
#
# 1. All twelve routes shared one budget, so a product's own status polling
#    could spend what its OTP send needs. Authentication sends are charged to
#    their own namespace, which nothing else in QCP touches.
# 2. **ASSUMPTION, and the go-live check for this file:** telling one caller
#    from another rests entirely on the reverse proxy. ``get_client_ip``
#    honours ``X-Forwarded-For`` only from a peer inside ``TRUSTED_PROXIES``;
#    slowapi's own ``get_remote_address`` never honours it at all, so behind
#    nginx every caller in the world arrived as 127.0.0.1 and the key
#    degenerated to the *unauthenticated* ``X-QCP-Product`` header — naming
#    ``quatafood`` was enough to spend its budget. The proxy in front of this
#    app must therefore (a) be inside ``TRUSTED_PROXIES`` and (b) **replace**
#    ``X-Forwarded-For`` rather than append to it (``proxy_set_header
#    X-Forwarded-For $remote_addr``), or the leftmost entry is caller-supplied
#    and the separation is decorative. The same assumption backs the audit
#    ``source_ip`` and the webhook rejection-collapse window.
def _qcp_rate_key(request: Request) -> str:
    slug = (request.headers.get("X-QCP-Product") or "").strip().casefold()[:40]
    caller = get_client_ip(request)
    if request.url.path.endswith(AUTH_SEND_PATH):
        return f"qcp-auth:{slug}:{caller}"
    return f"qcp:{slug}:{caller}"


QCP_RATE_LIMIT = "600/minute"


def _qcp_rate_limit_value() -> str:
    # A callable, so the limit is read per request rather than frozen at
    # import — which is what makes it testable.
    return QCP_RATE_LIMIT


@limiter.shared_limit(_qcp_rate_limit_value, "qcp", key_func=_qcp_rate_key)
async def qcp_rate_limit(request: Request) -> None:
    """Charge the request to its product's bucket before anything else runs.

    A ``@limiter.limit`` decorator on the endpoint executes *inside* the
    endpoint body, i.e. after ``Depends(current_product)`` has already spent a
    SELECT and a commit — so every credential guess cost two round trips, and
    the seven GET/lifecycle routes carried no limiter at all. As a dependency
    of ``current_product`` this runs before its first query and covers every
    QCP route at once — including the authentication send, which is charged to
    its own bucket by ``_qcp_rate_key`` but is limited by the same dependency,
    at the same point, so a credential guess there stays just as cheap.
    """
    return None


async def current_product(
    request: Request,
    _rate_limited: None = Depends(qcp_rate_limit),
    x_qcp_product: Optional[str] = Header(default=None, alias="X-QCP-Product"),
    x_qcp_key: Optional[str] = Header(default=None, alias="X-QCP-Key"),
    x_qcp_signature: Optional[str] = Header(default=None, alias="X-QCP-Signature"),
    x_qcp_timestamp: Optional[str] = Header(default=None, alias="X-QCP-Timestamp"),
    x_qcp_idempotency_key: Optional[str] = Header(
        default=None, alias="X-QCP-Idempotency-Key"
    ),
    db: Session = Depends(get_db),
) -> WhatsAppProduct:
    """Resolve and verify the calling product.

    An unknown product and a wrong key are indistinguishable — same status,
    same message, and the constant-time compare only runs against a real
    stored hash, so response timing does not answer "does this product
    exist?" either.

    The signature covers the *bound* request, not just its body. Signing
    ``f"{sent_at}." + body`` alone made one captured (timestamp, signature)
    pair valid for every route with the same body for the whole skew window —
    and every GET, ``/open``, ``/close`` and ``/return-to-ai`` has an empty
    body, so a single capture replayed against all of them. The verb, the
    routed path and ``X-QCP-Idempotency-Key`` (which chooses whether a send
    is a new message or a duplicate, and was entirely unsigned) are therefore
    part of the signed material.

    The query string is deliberately *not* signed: it would have to be
    canonicalised (encoding, parameter order) for two implementations to
    agree, and every state-changing route puts its target in the path, not
    the query. The residual is that a captured GET signature can be replayed
    against the same GET with a different filter — within the same product's
    own data, which that product may read anyway.
    """
    slug = (x_qcp_product or "").strip().lower()
    product = (
        db.query(WhatsAppProduct).filter(WhatsAppProduct.slug == slug).first()
        if slug
        else None
    )
    presented = _hash_key(x_qcp_key) if x_qcp_key else ""
    expected = product.api_key_hash if product else ""
    if not product or not presented or not hmac.compare_digest(expected, presented):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid QCP credentials")

    if settings_store.require_signature():
        raw_body = await request.body()
        if not x_qcp_signature or not x_qcp_timestamp:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing request signature")
        if not webhooks.is_sha256_hex(x_qcp_signature):
            # Shape first: ``compare_digest`` raises TypeError on a non-ASCII
            # str and Starlette decodes headers as latin-1, so this header can
            # otherwise turn a 401 into an unhandled 500.
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid request signature")
        try:
            sent_at = int(x_qcp_timestamp)
            # Inside the ``try``: a 400-digit timestamp parses fine and then
            # OverflowErrors on the float conversion below, which is a 500 on
            # a caller-controlled parse.
            skew = abs(time.time() - sent_at)
        except (ValueError, OverflowError):
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED, "Invalid signature timestamp"
            ) from None
        if skew > env_settings.WHATSAPP_SIGNATURE_SKEW_SECONDS:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Signature timestamp out of range")
        message = (
            f"{request.method.upper()}\n"
            f"{request.url.path}\n"
            f"{x_qcp_idempotency_key or ''}\n"
            f"{sent_at}."
        ).encode("utf-8") + raw_body
        digest = hmac.new(
            product.api_key_hash.encode("utf-8"), message, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(
            digest.encode("ascii"), x_qcp_signature.casefold().encode("ascii")
        ):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid request signature")

    product.last_seen_at = datetime.now(timezone.utc)
    db.commit()
    return product


def _require_enabled(db: Session, product: WhatsAppProduct) -> None:
    """Conversation + history endpoints are refused outright for a product
    that has not been migrated onto QCP.

    Sending is different: a send by a disabled product is *recorded* as a
    suppressed message so the product can see why nothing happened, which is
    what ``routing`` check 1 does. Reading another surface's data has no such
    reason to be soft.
    """
    if not product.is_enabled:
        audit.record(
            db,
            action="api.denied",
            resource_type="whatsapp_product",
            resource_id=product.slug,
            outcome=audit.OUTCOME_DENIED,
            reason="product_disabled",
            product_id=product.id,
        )
        db.commit()
        raise HTTPException(status.HTTP_403_FORBIDDEN, "product_disabled")


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------

def _message_out(row: WhatsAppMessage) -> MessageOut:
    return MessageOut(
        message_uid=row.message_uid,
        status=row.status,
        direction=row.direction,
        kind=row.kind,
        intent=row.intent,
        to=row.to_phone_e164,
        conversation_id=row.conversation_id,
        attempts=row.attempts or 0,
        error_code=row.error_code,
        last_error=row.last_error,
        suppressed_reason=row.suppressed_reason,
        created_at=row.created_at,
        sent_at=row.sent_at,
        delivered_at=row.delivered_at,
        read_at=row.read_at,
        failed_at=row.failed_at,
    )


def _conversation_out(row, *, product: Optional[WhatsAppProduct] = None) -> ConversationOut:
    """Serialise a thread for the product that asked for it.

    Two fields on this row are *not* about the caller when the caller is
    only a participant on a shared engagement thread:

    * ``assignee_id`` is a ``users.id`` that is, by construction, real,
      active and WhatsApp-entitled. ``conversations.assign`` deliberately
      answers every bad assignee with one indistinguishable error so a
      machine credential cannot walk user ids and learn that; reading the
      owner's agent straight off the row hands over the same thing.
    * ``unread_count`` counts inbound the *owner* has not read, so it
      reports how actively another company's customer is engaging with them.

    Both are blanked for a non-owner rather than the whole row being
    refused: a product must keep reading the thread its own messages are in.
    ``product=None`` means an internal/unscoped caller and blanks nothing.
    """
    owned = product is None or row.product_id == product.id
    return ConversationOut(
        id=row.id,
        phone_e164=row.phone_e164,
        display_name=row.display_name,
        state=row.state,
        assignee_id=row.assignee_id if owned else None,
        unread_count=(row.unread_count or 0) if owned else 0,
        locale=row.locale,
        last_inbound_at=row.last_inbound_at,
        last_outbound_at=row.last_outbound_at,
        service_window_expires_at=row.service_window_expires_at,
        service_window_open=conversations.service_window_open(row),
        created_at=row.created_at,
    )


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------

def _send(
    request: Request,
    db: Session,
    product: WhatsAppProduct,
    payload: MessageSendIn,
    *,
    expected_category: Optional[str],
    idempotency_key: Optional[str],
) -> JSONResponse:
    """Shared body for the canonical and the three category-scoped endpoints.

    Note what is *not* here: any decision about which account to use. This
    function hands the intent to ``dispatch.send`` and never sees an account
    until the resulting message row already exists.
    """
    from app.services.whatsapp import dispatch  # noqa: PLC0415 — see module docstring

    thread = None
    if payload.conversation_id is not None:
        # Ownership, not participation. Naming a thread is a claim to be
        # *in* that conversation, and for free-form it is a claim on the
        # service window somebody else's customer opened — the strongest
        # thing this API grants, since prose carries no approved template.
        # Participation is bought with one cheap utility send to a guessable
        # phone number, so it cannot be what unlocks this. A product with no
        # claim on the row simply omits ``conversation_id`` and sends its
        # template; only free-form needs the thread, and only the owner has
        # one here.
        thread = conversations.owned_by_product(
            db, product=product, conversation_id=payload.conversation_id
        )
        if thread is None:
            # Another product's thread, or none at all — indistinguishable.
            raise HTTPException(status.HTTP_404_NOT_FOUND, "conversation_not_found")
        if thread.phone_e164 != payload.to:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "conversation_phone_mismatch")
    elif payload.kind != "template":
        # Free-form has to reply *to* something. Requiring the thread is what
        # lets the 24h service window be checked at all.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "conversation_required")

    if payload.kind != "template" and not conversations.service_window_open(thread):
        # Meta refuses free-form outside the window and charges the attempt
        # against the number's quality rating. Refuse it locally instead.
        raise HTTPException(status.HTTP_409_CONFLICT, "outside_service_window")

    _assert_category(db, product, payload, expected_category)

    result = dispatch.send(
        product_slug=product.slug,
        intent=payload.intent,
        to_phone_e164=payload.to,
        kind=payload.kind,
        locale=payload.locale,
        variables=tuple(payload.variables),
        body=payload.body,
        reference=payload.reference,
        idempotency_key=idempotency_key,
        source_ip=get_client_ip(request),
    )

    message_uid = result.get("message_uid")
    if message_uid and not result.get("duplicate"):
        conversations.attach_outbound(
            db,
            product=product,
            message_uid=message_uid,
            phone_e164=payload.to,
            thread=thread,
        )
        db.commit()

    out = MessageAcceptedOut(
        message_uid=message_uid or "",
        status=result.get("status", "queued"),
        duplicate=bool(result.get("duplicate")),
        reason=result.get("reason"),
    )
    # A replay of an already-accepted send is 200; a first accept is 202.
    code = status.HTTP_200_OK if out.duplicate else status.HTTP_202_ACCEPTED
    return JSONResponse(out.model_dump(mode="json"), status_code=code)


def _preview_template(
    db: Session, *, product: WhatsAppProduct, intent: str, locale: Optional[str]
) -> Optional[WhatsAppTemplate]:
    """Read-only: which template *would* this intent resolve to, if any?

    Reuses ``routing``'s private selectors deliberately, so the answer here
    can never drift from the answer the choke point gives. Returns None
    whenever anything is unresolved — this function never decides that a
    send is allowed, only that a *declared category* contradicts a template
    that already exists.
    """
    rule = routing._find_rule(  # noqa: SLF001 — one selection implementation, not two
        db, product_id=product.id, intent=intent, locale=locale
    )
    if rule is None:
        return None
    account = (
        db.query(WhatsAppAccount)
        .filter(
            WhatsAppAccount.purpose == rule.purpose,
            WhatsAppAccount.is_active.is_(True),
        )
        .order_by(WhatsAppAccount.id)
        .first()
    )
    if account is None:
        return None
    language = (locale or product.default_locale or "en").strip() or "en"
    return routing._find_template(  # noqa: SLF001
        db, account_id=account.id, intent=rule.template_intent, language=language
    )


def _assert_category(
    db: Session,
    product: WhatsAppProduct,
    payload: MessageSendIn,
    expected_category: Optional[str],
) -> None:
    """Narrowing check behind ``/messages/{authentication,utility,marketing}``.

    The category-scoped endpoints let a product state what *kind* of message
    it believes it is sending. That statement can only ever **refuse** a
    send: it is compared against the template the routing rules already
    resolved, and plays no part in choosing one. If the route cannot be
    resolved here at all, this says nothing and lets
    ``routing.resolve_route`` produce the authoritative denial — duplicating
    denial semantics outside the choke point is exactly the bug the design
    warns about.
    """
    if expected_category is None:
        return
    template = _preview_template(
        db, product=product, intent=payload.intent, locale=payload.locale
    )
    if template is None or template.category == expected_category:
        return
    audit.record(
        db,
        action="routing.denied",
        resource_type="whatsapp_route",
        resource_id=f"{product.slug}:{payload.intent}",
        outcome=audit.OUTCOME_DENIED,
        reason="category_mismatch",
        product_id=product.id,
        account_id=template.account_id,
        details={
            "intent": payload.intent,
            "declared": expected_category,
            "actual": template.category,
        },
    )
    db.commit()
    raise HTTPException(status.HTTP_409_CONFLICT, "category_mismatch")


@router.post("/whatsapp/messages")
async def send_message(
    request: Request,
    payload: MessageSendIn,
    db: Session = Depends(get_db),
    product: WhatsAppProduct = Depends(current_product),
    x_qcp_idempotency_key: Optional[str] = Header(default=None, alias="X-QCP-Idempotency-Key"),
):
    """Send one message. The account is resolved from the intent, never asked for."""
    return _send(
        request,
        db,
        product,
        payload,
        expected_category=None,
        idempotency_key=x_qcp_idempotency_key,
    )


@router.post("/whatsapp/messages/authentication")
async def send_authentication(
    request: Request,
    payload: MessageSendIn,
    db: Session = Depends(get_db),
    product: WhatsAppProduct = Depends(current_product),
    x_qcp_idempotency_key: Optional[str] = Header(default=None, alias="X-QCP-Idempotency-Key"),
):
    """Send an authentication message (OTP, login code, PIN reset, device check).

    The category is an assertion about what the caller believes it is
    sending, checked against the template the routing rules resolved. It
    cannot move the message onto a different number — if the resolved
    template is not an ``authentication`` template the send is refused.
    """
    return _send(
        request,
        db,
        product,
        payload,
        expected_category="authentication",
        idempotency_key=x_qcp_idempotency_key,
    )


@router.post("/whatsapp/messages/utility")
async def send_utility(
    request: Request,
    payload: MessageSendIn,
    db: Session = Depends(get_db),
    product: WhatsAppProduct = Depends(current_product),
    x_qcp_idempotency_key: Optional[str] = Header(default=None, alias="X-QCP-Idempotency-Key"),
):
    """Send a utility message (order updates, delivery, transaction receipts)."""
    return _send(
        request,
        db,
        product,
        payload,
        expected_category="utility",
        idempotency_key=x_qcp_idempotency_key,
    )


@router.post("/whatsapp/messages/marketing")
async def send_marketing(
    request: Request,
    payload: MessageSendIn,
    db: Session = Depends(get_db),
    product: WhatsAppProduct = Depends(current_product),
    x_qcp_idempotency_key: Optional[str] = Header(default=None, alias="X-QCP-Idempotency-Key"),
):
    """Send a marketing message.

    Structurally incapable of reaching Quata Verify: a marketing template
    cannot exist on an authentication account
    (``ck_whatsapp_templates_marketing_never_on_verify``), and
    ``resolve_route`` refuses ``marketing_on_auth_account`` before that.
    """
    return _send(
        request,
        db,
        product,
        payload,
        expected_category="marketing",
        idempotency_key=x_qcp_idempotency_key,
    )


@router.get("/whatsapp/messages/{message_uid}", response_model=MessageOut)
def get_message(
    message_uid: str,
    db: Session = Depends(get_db),
    product: WhatsAppProduct = Depends(current_product),
):
    """One message, scoped to the calling product."""
    row = (
        db.query(WhatsAppMessage)
        .filter(
            WhatsAppMessage.message_uid == message_uid,
            WhatsAppMessage.product_id == product.id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "message_not_found")
    return _message_out(row)


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

@router.get("/whatsapp/conversations", response_model=list[ConversationOut])
def list_conversations(
    state: Optional[str] = Query(default=None, max_length=20),
    phone: Optional[str] = Query(default=None, max_length=24),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    product: WhatsAppProduct = Depends(current_product),
):
    _require_enabled(db, product)
    rows = conversations.list_for_product(
        db,
        product=product,
        state=state,
        phone_e164=conversations.phone_e164_for(phone) if phone else None,
        limit=limit,
        offset=offset,
    )
    return [_conversation_out(r, product=product) for r in rows]


def _readable(db: Session, product: WhatsAppProduct, conversation_id: int):
    """A thread this product may look at: it owns it, or has a message in it.

    Both answers are 404 rather than 403 — a product must not be able to
    learn that another product's conversation exists.
    """
    row = conversations.for_product(db, product=product, conversation_id=conversation_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "conversation_not_found")
    return row


def _owned(db: Session, product: WhatsAppProduct, conversation_id: int):
    """A thread this product may *change*. Ownership only, not participation.

    ``state``, ``unread_count`` and ``assignee_id`` are one row shared by
    every product on the engagement number, so the state verbs cannot ride on
    the read rule: one cheap utility send to a guessable phone number is all
    it takes to become a participant, and that must not buy the power to
    close another product's live customer thread or take its agent off it.
    See ``conversations.owned_by_product``.
    """
    row = conversations.owned_by_product(
        db, product=product, conversation_id=conversation_id
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "conversation_not_found")
    return row


@router.get("/whatsapp/conversations/{conversation_id}", response_model=ConversationOut)
def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    product: WhatsAppProduct = Depends(current_product),
):
    _require_enabled(db, product)
    return _conversation_out(_readable(db, product, conversation_id), product=product)


@router.post("/whatsapp/conversations/{conversation_id}/open", response_model=ConversationOut)
def open_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    product: WhatsAppProduct = Depends(current_product),
):
    _require_enabled(db, product)
    row = conversations.open_conversation(db, _owned(db, product, conversation_id))
    audit.record(
        db,
        action="conversation.opened",
        resource_type="whatsapp_conversation",
        resource_id=str(row.id),
        product_id=product.id,
        account_id=row.account_id,
    )
    db.commit()
    return _conversation_out(row)


@router.post("/whatsapp/conversations/{conversation_id}/close", response_model=ConversationOut)
def close_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    product: WhatsAppProduct = Depends(current_product),
):
    _require_enabled(db, product)
    row = conversations.close_conversation(db, _owned(db, product, conversation_id))
    audit.record(
        db,
        action="conversation.closed",
        resource_type="whatsapp_conversation",
        resource_id=str(row.id),
        product_id=product.id,
        account_id=row.account_id,
    )
    db.commit()
    return _conversation_out(row)


@router.post("/whatsapp/conversations/{conversation_id}/assign", response_model=ConversationOut)
def assign_conversation(
    conversation_id: int,
    payload: ConversationAssignIn,
    db: Session = Depends(get_db),
    product: WhatsAppProduct = Depends(current_product),
):
    """Put a human agent on the thread."""
    _require_enabled(db, product)
    row = _owned(db, product, conversation_id)
    try:
        conversations.assign(db, row, user_id=payload.assignee_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    audit.record(
        db,
        action="conversation.assigned",
        resource_type="whatsapp_conversation",
        resource_id=str(row.id),
        product_id=product.id,
        account_id=row.account_id,
        details={"assignee_id": payload.assignee_id},
    )
    db.commit()
    return _conversation_out(row)


@router.post(
    "/whatsapp/conversations/{conversation_id}/return-to-ai", response_model=ConversationOut
)
def return_conversation_to_ai(
    conversation_id: int,
    db: Session = Depends(get_db),
    product: WhatsAppProduct = Depends(current_product),
):
    """Take the human off the thread and reopen it for automation.

    v1 clears ``assignee_id`` only. ``assigned_agent`` is the AI-routing
    seam and is deliberately left NULL — nothing downstream may start
    depending on a half-defined value.
    """
    _require_enabled(db, product)
    row = conversations.return_to_ai(db, _owned(db, product, conversation_id))
    audit.record(
        db,
        action="conversation.returned_to_ai",
        resource_type="whatsapp_conversation",
        resource_id=str(row.id),
        product_id=product.id,
        account_id=row.account_id,
    )
    db.commit()
    return _conversation_out(row)


@router.get(
    "/whatsapp/conversations/{conversation_id}/messages",
    response_model=ConversationHistoryOut,
)
def conversation_history(
    conversation_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    before_id: Optional[int] = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    product: WhatsAppProduct = Depends(current_product),
):
    """Message history for one of the product's own conversations.

    Reachable, not owned: a product that has a message in a shared thread
    must still be able to read *its own* messages out of it. What it sees is
    scoped a second time below, on ``whatsapp_messages.product_id``.
    """
    _require_enabled(db, product)
    row = _readable(db, product, conversation_id)
    rows = conversations.history(
        db, row, limit=limit, before_id=before_id, product_id=product.id
    )
    return ConversationHistoryOut(
        conversation_id=row.id,
        messages=[_message_out(m) for m in rows],
        next_before_id=rows[-1].id if len(rows) == limit else None,
    )


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@router.get("/whatsapp/health", response_model=ProductHealthOut)
def product_health(
    db: Session = Depends(get_db),
    product: WhatsAppProduct = Depends(current_product),
):
    """Readiness, from the calling product's point of view.

    Says *whether* a purpose is reachable, never which number backs it — a
    product has no business knowing that, and telling it would hand a caller
    the vocabulary to start asking for one.
    """
    allowed = [str(p) for p in (product.allowed_purposes or [])]
    available = {
        purpose: db.query(WhatsAppAccount)
        .filter(
            WhatsAppAccount.purpose == purpose,
            WhatsAppAccount.is_active.is_(True),
        )
        .first()
        is not None
        for purpose in allowed
    }
    intents = [
        r.intent
        for r in db.query(WhatsAppRoutingRule)
        .filter(
            WhatsAppRoutingRule.product_id == product.id,
            WhatsAppRoutingRule.is_active.is_(True),
        )
        .order_by(WhatsAppRoutingRule.intent)
        .all()
    ]
    delivery = settings_store.delivery_enabled()
    return ProductHealthOut(
        ok=bool(product.is_enabled and delivery and any(available.values())),
        product=product.slug,
        enabled=product.is_enabled,
        delivery_enabled=delivery,
        allowed_purposes=allowed,
        purpose_available=available,
        active_intents=sorted(set(intents)),
    )


# ---------------------------------------------------------------------------
# Meta-facing webhook
# ---------------------------------------------------------------------------
#
# One URL per account, because the signature is verified with *that*
# account's app secret — a payload for one number must never be ingestible
# under the other's slug.
#
# The status-code contract is not arbitrary:
#
#   403  the request is not Meta (bad/missing X-Hub-Signature-256, wrong
#        hub.verify_token). Answering 200 to an unauthenticated caller would
#        accept forged traffic and hand an attacker a probe.
#   404  no account owns this slug, so there is no secret to verify against.
#   200  everything else — *including* a payload we cannot parse. Meta
#        disables a subscription whose endpoint keeps erroring, so a body we
#        will never understand is recorded and acknowledged, not retried
#        forever.
#
# Deliberately not rate-limited: Meta bursts hard on redelivery and shedding
# those requests is precisely how a subscription gets disabled. The abuse
# controls are the body-size cap in ``webhooks.MAX_BODY_BYTES`` and the
# rejection-collapse window in ``webhooks._reject``, which stops a forged
# burst from using the audit log as an unmetered INSERT.

@router.get("/whatsapp/webhook/{account_slug}")
def whatsapp_webhook_verify(
    account_slug: str,
    request: Request,
    hub_mode: Optional[str] = Query(default=None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(default=None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(default=None, alias="hub.challenge"),
    db: Session = Depends(get_db),
):
    """Meta's subscription handshake.

    The challenge comes back as the raw response body — Meta compares it byte
    for byte, so this returns ``text/plain`` and never JSON.
    """
    try:
        challenge = webhooks.verify_subscription(
            db,
            account_slug=account_slug,
            mode=hub_mode,
            token=hub_verify_token,
            challenge=hub_challenge,
            source_ip=get_client_ip(request),
        )
    except webhooks.WebhookRejected as exc:
        return PlainTextResponse(exc.reason, status_code=exc.http_status)
    return PlainTextResponse(challenge)


@router.post("/whatsapp/webhook/{account_slug}")
async def whatsapp_webhook_receive(
    account_slug: str,
    request: Request,
    x_hub_signature_256: Optional[str] = Header(default=None, alias="X-Hub-Signature-256"),
    db: Session = Depends(get_db),
):
    """Ingest one webhook envelope from Meta.

    The signature covers the **raw** body, so the bytes are read here and
    passed down untouched — re-serialising a parsed model would change them
    and every signature would fail.
    """
    raw_body = await request.body()
    try:
        counters = webhooks.handle_event(
            db,
            account_slug=account_slug,
            raw_body=raw_body,
            signature_header=x_hub_signature_256,
            source_ip=get_client_ip(request),
        )
    except webhooks.WebhookRejected as exc:
        return JSONResponse({"ok": False, "reason": exc.reason}, status_code=exc.http_status)
    except Exception:  # noqa: BLE001 — never 500 at Meta; that disables the hook
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
        log.exception("whatsapp.webhook_unhandled", extra={"account": account_slug})
        return JSONResponse({"ok": True, "handled": False}, status_code=200)
    return JSONResponse({"ok": True, **counters}, status_code=200)
