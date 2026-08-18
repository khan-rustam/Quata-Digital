"""QCP — the admin console's read and write surface.

The product-facing gateway lives in ``routes_whatsapp.py`` and is
authenticated with ``X-QCP-Product``/``X-QCP-Key``. Nothing there is usable
from the admin console, and nothing here is usable by a product.

**Two permissions, because one of them was doing two jobs.** Most routes
below are gated on ``settings:manage`` exactly like ``/admin/alerts/*``
(``routes_notifications.py:204``) — reading the estate, storing credentials,
registering a product, correcting its details. Five are not: switching a
number on or off, minting or revoking a product's gateway key, and granting a
product the authentication purpose take ``whatsapp:operate`` instead. Every
Admin holds ``settings:manage``; it is the permission for "edit the site's
contact address", and it should not also be the permission for switching on
the number that carries the fleet's login codes. See ``PERM_OPERATE`` below
for the full list and the one deliberate bypass.

**It never returns a secret.** ``whatsapp_accounts`` stores three
Fernet-encrypted columns and ``whatsapp_products`` stores a key *hash*. This
module returns booleans about them (``has_access_token``, ``has_api_key``), a
length, and a short one-way fingerprint — never a value, never a ciphertext,
and never "just the first few characters". ``_account_out``, ``_product_out``,
``_account_admin_out`` and ``_product_admin_out`` are the only shapes that
leave here, so the property is checked in four places rather than at every
call site. The one plaintext this module ever emits is a *just-minted*
product key, which it generates, returns once, and never stores.

**Nothing here switches QCP on as a side effect.** QCP ships dormant — two
accounts with ``is_active=False``, four products with ``is_enabled=False``,
delivery off — and that stayed true when the write surface arrived. There are
exactly four routes that change a switch (``accounts/{slug}/enable`` and
``disable``, ``products/{slug}/enable`` and ``disable``), each does nothing
else, and enabling a *number* — the act that lets QCP address Meta at all —
additionally requires the account to be fully configured and the operator to
type its slug back with a written justification. Setting credentials,
registering a product, minting a key and reassigning a conversation all leave
every gate exactly where they found it.

**Every write is audited and every refusal is a refusal, not a 500.** Each
route below records who, what, when and — for a credential — the old
fingerprint and the new one, in ``whatsapp_audit_log``. The storage engine
refuses a second active number per purpose and a duplicate product slug;
those come back as a 409 naming what is in the way, with the denial itself
audited, because an IntegrityError traceback tells an operator nothing they
can act on. Every ``_deny`` call site below is one of those.

Why the write surface exists at all: ``whatsapp_templates.category`` was
operator-typed data that no form validated, so a ``utility`` row could sit on
the Quata Verify number and Meta re-classifying it to ``MARKETING`` would
never be noticed. The CHECK constraint stops the row. Only a real write API
stops the practice of configuring this platform with hand-written INSERTs.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, require_permission
from app.core.config import settings as env_settings
from app.db.session import get_db
from app.models import (
    User,
    WhatsAppAccount,
    WhatsAppAuditLog,
    WhatsAppConversation,
    WhatsAppMessage,
    WhatsAppProduct,
    WhatsAppRoutingRule,
    WhatsAppTemplate,
)
from app.models.whatsapp import PURPOSE_AUTHENTICATION, PURPOSE_ENGAGEMENT
from app.schemas.whatsapp_admin import (
    AccountAdminOut,
    AccountCredentialsIn,
    AccountEnableIn,
    ApiKeyMintedOut,
    ConnectionTestOut,
    ConversationReassignIn,
    ConversationReassignOut,
    CredentialStateOut,
    ProductAdminOut,
    ProductAuthenticationGrantIn,
    ProductPurposesIn,
    ProductRegisterIn,
    SecurityWarningOut,
)
from app.services.whatsapp import audit
from app.services.whatsapp import conversations as conversations_service
from app.services.whatsapp import credentials as wa_credentials
from app.services.whatsapp import registry as registry_service
from app.services.whatsapp import settings_store


router = APIRouter(tags=["whatsapp-admin"])

# The console permission. Every Admin holds it, and it is the same one that
# gates the site's contact address and the alert centre — which is the right
# ticket for reading this estate, storing a credential, registering a product
# and correcting its details.
PERM = "settings:manage"

# The fleet permission. Five routes take it instead:
#
#   POST   /admin/qcp/accounts/{slug}/enable
#   POST   /admin/qcp/accounts/{slug}/disable
#   POST   /admin/qcp/products/{slug}/api-key
#   DELETE /admin/qcp/products/{slug}/api-key
#   POST   /admin/qcp/products/{slug}/purposes/authentication
#
# Those are the actions whose blast radius is the whole fleet rather than this
# website: switching on the number that carries QuataFood's login OTP,
# payment-PIN reset and phone-change verification (none of which have an email
# fallback, so a Meta restriction on that number is an account lockout);
# minting or retiring the credential a product authenticates with; and putting
# a product's traffic next to the authentication path. "Can edit site
# settings" is not the same claim as any of those, and it was covering all of
# them.
#
# These routes name **only** this permission. ``require_permission`` is an OR
# over the names it is given, so naming ``PERM`` alongside would leave the
# split decorative. The one bypass is ``*``, which ``deps.user_permissions``
# adds for the ``super_admin`` role — deliberate, and what keeps the
# commissioning flow completable by the person who is meant to run it.
PERM_OPERATE = "whatsapp:operate"

# A template whose Meta category does not match the account it is bound to.
# The storage engine already forbids all of these (see
# ``ck_whatsapp_templates_auth_only_on_verify``,
# ``ck_whatsapp_templates_marketing_never_on_verify`` and
# ``ck_whatsapp_templates_verify_is_auth_only``), so this should always be
# false. It is computed and surfaced anyway: if it is ever true, either a
# constraint was dropped or the row predates one, and that is precisely the
# thing an operator must see immediately rather than infer.
#
# The second rule is deliberately "anything but authentication", not just
# "marketing": a ``utility`` row on Quata Verify is exactly the legacy shape
# the newest CHECK was added to forbid, and it is the one an operator would
# otherwise never be shown.
def _is_misbound(category: str, account_purpose: str) -> bool:
    if category == "authentication" and account_purpose != "authentication":
        return True
    if category != "authentication" and account_purpose == "authentication":
        return True
    return False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _account_out(row: WhatsAppAccount) -> dict:
    """Public shape of an account. Credentials become booleans here."""
    return {
        "id": row.id,
        "slug": row.slug,
        "name": row.name,
        "purpose": row.purpose,
        "display_phone": row.display_phone or None,
        "api_version": row.api_version,
        "is_active": row.is_active,
        "health": row.health,
        "quality_rating": row.quality_rating,
        "messaging_limit": row.messaging_limit,
        "last_checked_at": row.last_checked_at,
        "last_error": row.last_error,
        # Presence only — never the value, never the ciphertext.
        "has_phone_number_id": bool(row.phone_number_id),
        "has_waba_id": bool(row.waba_id),
        "has_access_token": bool(row.access_token_encrypted),
        "has_app_secret": bool(row.app_secret_encrypted),
        "has_verify_token": bool(row.webhook_verify_token_encrypted),
        # "Configured" means it could address Meta at all. It says nothing
        # about whether it is switched on — that is is_active.
        "configured": bool(
            row.phone_number_id and row.waba_id and row.access_token_encrypted
        ),
        # Configuration states that are a security posture rather than a blank
        # field — see ``_account_security``. Carried on the *read* shape too,
        # not only on the write shape, because the overview is the screen an
        # operator opens; a critical that only appears in the response to a
        # credentials write is one nobody sees until they were already editing.
        "security": [w.model_dump() for w in _account_security(row)],
    }


def _product_out(row: WhatsAppProduct) -> dict:
    return {
        "id": row.id,
        "slug": row.slug,
        "name": row.name,
        "description": row.description,
        "is_enabled": row.is_enabled,
        # An empty api_key_hash means no key has ever been minted: no sha256
        # digest can equal "", so such a product cannot authenticate.
        "has_api_key": bool(row.api_key_hash),
        "api_key_prefix": row.api_key_prefix or None,
        "allowed_purposes": row.allowed_purposes or [],
        "default_locale": row.default_locale,
        "rate_limit_per_minute": row.rate_limit_per_minute,
        # ``has_webhook`` / ``webhook_url`` / ``has_webhook_secret`` used to be
        # reported here and rendered by the products screen under "Callback
        # webhook". Nothing writes ``whatsapp_products.webhook_url`` — not this
        # module, not the seeder, not the gateway — and nothing reads it: QCP
        # has no outbound callback path at all. The row was permanently "not
        # configured" and always would be, so an operator reading it reasonably
        # concluded a callback could be configured somewhere. Removed rather
        # than made settable: a stored callback address nothing ever calls is a
        # louder lie than an empty one. The columns are left on the model as
        # the seam they were meant to be; when a callback path exists, this is
        # where it comes back.
        "registry_version": row.registry_version,
        "last_seen_at": row.last_seen_at,
        "created_at": row.created_at,
    }


def _counts_by(db: Session, column, model, **filters) -> dict:
    q = db.query(column, func.count(model.id))
    for attr, value in filters.items():
        q = q.filter(getattr(model, attr) == value)
    return {key: count for key, count in q.group_by(column).all()}


# ---------------------------------------------------------------------------
# Overview — "is it on, and is it working"
# ---------------------------------------------------------------------------

@router.get("/admin/qcp/overview")
def qcp_overview(
    hours: int = Query(default=24, ge=1, le=720),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM)),
):
    """Everything the QCP overview screen needs in one call.

    The three dormancy gates are reported separately and unresolved, because
    "why is nothing sending" has three different answers and collapsing them
    into one boolean is what makes an operator flip the wrong switch.
    """
    since = _now() - timedelta(hours=hours)

    accounts = db.query(WhatsAppAccount).order_by(WhatsAppAccount.purpose).all()
    products = db.query(WhatsAppProduct).order_by(WhatsAppProduct.slug).all()

    by_status = _counts_by(db, WhatsAppMessage.status, WhatsAppMessage)
    recent_status = {
        key: count
        for key, count in db.query(WhatsAppMessage.status, func.count(WhatsAppMessage.id))
        .filter(WhatsAppMessage.created_at >= since)
        .group_by(WhatsAppMessage.status)
        .all()
    }
    queued_total = by_status.get("queued", 0) + by_status.get("sending", 0)
    oldest_queued = (
        db.query(func.min(WhatsAppMessage.created_at))
        .filter(WhatsAppMessage.status.in_(("queued", "sending")))
        .scalar()
    )

    template_counts = _counts_by(db, WhatsAppTemplate.status, WhatsAppTemplate)

    failures = (
        db.query(WhatsAppMessage)
        .filter(WhatsAppMessage.status.in_(("failed", "suppressed")))
        .order_by(WhatsAppMessage.id.desc())
        .limit(10)
        .all()
    )
    product_names = {p.id: p.slug for p in products}

    denials = (
        db.query(WhatsAppAuditLog)
        .filter(WhatsAppAuditLog.outcome.in_(("denied", "error")))
        .order_by(WhatsAppAuditLog.id.desc())
        .limit(10)
        .all()
    )

    return {
        "window_hours": hours,
        "gates": {
            # Gate 1 — the environment kill switch. Nothing in the console
            # can override it; it needs a .env change and a restart.
            "env_enabled": bool(env_settings.WHATSAPP_ENABLED),
            # Gate 2 — the site setting, toggleable by an admin.
            "delivery_enabled": settings_store.delivery_enabled(),
            # Gate 3 — per-account and per-product switches, both default off.
            "any_account_active": any(a.is_active for a in accounts),
            "any_product_enabled": any(p.is_enabled for p in products),
            "require_signature": settings_store.require_signature(),
        },
        "accounts": [_account_out(a) for a in accounts],
        "products": [_product_out(p) for p in products],
        "queue": {
            "queued": queued_total,
            "oldest_queued_at": oldest_queued,
            "failed": by_status.get("failed", 0),
            "suppressed": by_status.get("suppressed", 0),
            "total": sum(by_status.values()),
        },
        "recent": {
            "total": sum(recent_status.values()),
            "sent": recent_status.get("sent", 0)
            + recent_status.get("delivered", 0)
            + recent_status.get("read", 0),
            "queued": recent_status.get("queued", 0) + recent_status.get("sending", 0),
            "failed": recent_status.get("failed", 0),
            "suppressed": recent_status.get("suppressed", 0),
        },
        "templates": {
            "total": sum(template_counts.values()),
            "approved": template_counts.get("approved", 0),
            "pending_approval": template_counts.get("pending_approval", 0),
            "rejected": template_counts.get("rejected", 0),
        },
        "conversations": {
            "total": db.query(func.count(WhatsAppConversation.id)).scalar() or 0,
            "open": db.query(func.count(WhatsAppConversation.id))
            .filter(WhatsAppConversation.state == "open")
            .scalar()
            or 0,
        },
        "failures": [
            {
                "message_uid": m.message_uid,
                "status": m.status,
                "intent": m.intent,
                "product": product_names.get(m.product_id),
                "to": m.to_phone_e164,
                "attempts": m.attempts,
                "max_attempts": m.max_attempts,
                "error_code": m.error_code,
                "last_error": m.last_error,
                "suppressed_reason": m.suppressed_reason,
                "created_at": m.created_at,
            }
            for m in failures
        ],
        "denials": [
            {
                "id": a.id,
                "action": a.action,
                "outcome": a.outcome,
                "reason": a.reason,
                "product": product_names.get(a.product_id),
                "resource_type": a.resource_type,
                "resource_id": a.resource_id,
                "created_at": a.created_at,
            }
            for a in denials
        ],
    }


# ---------------------------------------------------------------------------
# Conversations — the agent console
# ---------------------------------------------------------------------------

def _conversation_out(
    row: WhatsAppConversation,
    *,
    account: Optional[WhatsAppAccount],
    product_slug: Optional[str],
) -> dict:
    return {
        "id": row.id,
        "phone_e164": row.phone_e164,
        "display_name": row.display_name,
        "state": row.state,
        "product": product_slug,
        "account": account.slug if account else None,
        "account_name": account.name if account else None,
        "account_purpose": account.purpose if account else None,
        "assignee_id": row.assignee_id,
        "unread_count": row.unread_count,
        "locale": row.locale,
        "last_inbound_at": row.last_inbound_at,
        "last_outbound_at": row.last_outbound_at,
        "service_window_expires_at": row.service_window_expires_at,
        "service_window_open": conversations_service.service_window_open(row),
        "created_at": row.created_at,
    }


def _message_out(row: WhatsAppMessage, *, product_slug: Optional[str]) -> dict:
    """A message as the console sees it.

    ``body`` and ``variables`` are already redacted at write time — an OTP is
    persisted as ``{"code": "sha256:…"}`` — so they are safe to return as
    stored. Nothing is un-redacted here.
    """
    return {
        "id": row.id,
        "message_uid": row.message_uid,
        "direction": row.direction,
        "kind": row.kind,
        "status": row.status,
        "intent": row.intent,
        "product": product_slug,
        "account_purpose": row.account_purpose,
        "body": row.body,
        "variables": row.variables or {},
        "to": row.to_phone_e164,
        "from": row.from_phone_e164,
        "attempts": row.attempts,
        "max_attempts": row.max_attempts,
        "error_code": row.error_code,
        "last_error": row.last_error,
        "suppressed_reason": row.suppressed_reason,
        "created_at": row.created_at,
        "sent_at": row.sent_at,
        "delivered_at": row.delivered_at,
        "read_at": row.read_at,
        "failed_at": row.failed_at,
    }


@router.get("/admin/qcp/conversations")
def qcp_conversations(
    product: Optional[str] = None,
    state: Optional[str] = None,
    account: Optional[str] = None,
    q: Optional[str] = Query(default=None, max_length=120),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM)),
):
    """Inbox across every product and both numbers.

    Unlike the product-facing list, this is not scoped to one product — the
    console is the one place that legitimately sees the whole estate.
    """
    accounts = {a.id: a for a in db.query(WhatsAppAccount).all()}
    products = {p.id: p for p in db.query(WhatsAppProduct).all()}
    by_slug = {p.slug: p for p in products.values()}

    query = db.query(WhatsAppConversation)
    if product:
        matched = by_slug.get(product)
        if not matched:
            # An unknown product filter must not silently widen to "all".
            return {"total": 0, "page": page, "page_size": page_size, "items": []}
        query = query.filter(WhatsAppConversation.product_id == matched.id)
    if state:
        query = query.filter(WhatsAppConversation.state == state)
    if account:
        matched_account = next((a for a in accounts.values() if a.slug == account), None)
        if not matched_account:
            return {"total": 0, "page": page, "page_size": page_size, "items": []}
        query = query.filter(WhatsAppConversation.account_id == matched_account.id)
    if q:
        needle = f"%{q.lower()}%"
        query = query.filter(
            or_(
                func.lower(WhatsAppConversation.phone_e164).like(needle),
                func.lower(WhatsAppConversation.display_name).like(needle),
            )
        )

    total = query.count()
    rows = (
        query.order_by(WhatsAppConversation.last_inbound_at.desc().nullslast(),
                       WhatsAppConversation.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            _conversation_out(
                r,
                account=accounts.get(r.account_id),
                product_slug=products[r.product_id].slug if r.product_id in products else None,
            )
            for r in rows
        ],
    }


@router.get("/admin/qcp/conversations/{conversation_id}")
def qcp_conversation_detail(
    conversation_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    before_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM)),
):
    """One thread, newest-first, with the delivery state of every message."""
    row = db.get(WhatsAppConversation, conversation_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")

    account = db.get(WhatsAppAccount, row.account_id)
    products = {p.id: p.slug for p in db.query(WhatsAppProduct).all()}
    # No product_id scope: the console sees the whole thread.
    messages = conversations_service.history(db, row, limit=limit, before_id=before_id)
    return {
        "conversation": _conversation_out(
            row,
            account=account,
            product_slug=products.get(row.product_id),
        ),
        "messages": [
            _message_out(m, product_slug=products.get(m.product_id)) for m in messages
        ],
        "next_before_id": messages[-1].id if len(messages) == limit else None,
    }


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

@router.get("/admin/qcp/templates")
def qcp_templates(
    account: Optional[str] = None,
    category: Optional[str] = None,
    template_status: Optional[str] = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM)),
):
    """Every template, with the account it is bound to for life.

    ``misbound`` is the load-bearing field: an authentication template must
    live on Quata Verify and a marketing template must never live there.
    """
    accounts = {a.id: a for a in db.query(WhatsAppAccount).all()}
    products = {p.id: p.slug for p in db.query(WhatsAppProduct).all()}

    query = db.query(WhatsAppTemplate)
    if account:
        matched = next((a for a in accounts.values() if a.slug == account), None)
        if not matched:
            return {"items": [], "accounts": [], "misbound_count": 0}
        query = query.filter(WhatsAppTemplate.account_id == matched.id)
    if category:
        query = query.filter(WhatsAppTemplate.category == category)
    if template_status:
        query = query.filter(WhatsAppTemplate.status == template_status)

    rows = query.order_by(
        WhatsAppTemplate.account_id, WhatsAppTemplate.category, WhatsAppTemplate.name
    ).all()

    items = []
    for r in rows:
        acct = accounts.get(r.account_id)
        items.append(
            {
                "id": r.id,
                "name": r.name,
                "language": r.language,
                "category": r.category,
                "intent": r.intent,
                "status": r.status,
                "account": acct.slug if acct else None,
                "account_name": acct.name if acct else None,
                "account_purpose": r.account_purpose,
                "account_is_active": acct.is_active if acct else False,
                "product": products.get(r.product_id),
                "variables": r.variables or [],
                "provider_template_id": r.provider_template_id,
                "rejection_reason": r.rejection_reason,
                "last_synced_at": r.last_synced_at,
                "created_at": r.created_at,
                "misbound": _is_misbound(r.category, r.account_purpose),
            }
        )

    return {
        "items": items,
        "accounts": [
            {
                "slug": a.slug,
                "name": a.name,
                "purpose": a.purpose,
                "is_active": a.is_active,
                "display_phone": a.display_phone or None,
            }
            for a in sorted(accounts.values(), key=lambda a: a.purpose)
        ],
        "misbound_count": sum(1 for i in items if i["misbound"]),
    }


# ---------------------------------------------------------------------------
# Products — the plugin registry
# ---------------------------------------------------------------------------

@router.get("/admin/qcp/products")
def qcp_products(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM)),
):
    """The registry: who is registered, whether they hold a key, and whether
    they are switched on. The key value itself does not exist anywhere — only
    its sha256 and a display prefix are stored."""
    products = db.query(WhatsAppProduct).order_by(WhatsAppProduct.slug).all()

    rules_total = _counts_by(db, WhatsAppRoutingRule.product_id, WhatsAppRoutingRule)
    rules_active = _counts_by(
        db, WhatsAppRoutingRule.product_id, WhatsAppRoutingRule, is_active=True
    )
    templates_total = _counts_by(db, WhatsAppTemplate.product_id, WhatsAppTemplate)
    messages_total = _counts_by(db, WhatsAppMessage.product_id, WhatsAppMessage)

    items = []
    for p in products:
        item = _product_out(p)
        item["routing_rules"] = rules_total.get(p.id, 0)
        item["routing_rules_active"] = rules_active.get(p.id, 0)
        item["templates"] = templates_total.get(p.id, 0)
        item["messages"] = messages_total.get(p.id, 0)
        # Why this product sends nothing, in the words its own sends are
        # refused with. The counts above are inputs to that judgement, not the
        # judgement: ``routing_rules_active: 3`` beside ``templates: 3`` reads
        # like a working product right up until every send comes back
        # ``template_not_approved`` because Meta has approved none of them.
        # ``include_key_gate`` is on here and only here — this is the surface
        # that can safely say a product holds no key.
        item["blocked_by"] = registry_service.product_gates(
            db, p, include_key_gate=True
        )
        items.append(item)

    return {
        "items": items,
        "platform_templates": templates_total.get(None, 0),
    }


# ===========================================================================
# THE WRITE SURFACE
# ===========================================================================
#
# Everything above answers "what is QCP doing". Everything below changes it.
# The shared machinery comes first: how a credential is described without
# being disclosed, how a refusal is recorded, and how the two IntegrityErrors
# this surface can provoke are turned into sentences.


# ---------------------------------------------------------------------------
# Fingerprints and key material
# ---------------------------------------------------------------------------

# ``sha256(value)[:12]``. Answers exactly one question — *is this the same
# value as before?* — which is what lets the audit trail record a credential
# change as ``old → new`` without the audit trail ever holding a credential,
# and lets an operator confirm the token they pasted is the token that is
# stored without either of them printing it.
#
# Twelve hex characters rather than the eight used for message-variable
# digests: those compare one short numeric OTP against one known row, while
# these are compared across every credential of every account for the life of
# the platform, and the extra 16 bits are free. Nothing authenticates against
# a fingerprint, and the values fingerprinted here are high-entropy provider
# tokens, so a truncated unsalted digest is not a guessing oracle the way a
# digest of a human-chosen secret would be.
def _fingerprint(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _fingerprint_stored(stored: Optional[str]) -> Optional[str]:
    """Fingerprint of an encrypted-at-rest credential.

    Fingerprints the *plaintext*, deliberately: a Fernet ciphertext carries a
    timestamp and a random IV, so two encryptions of one token differ and a
    fingerprint of the ciphertext would report every re-save as a change.
    """
    return _fingerprint(wa_credentials.decrypt_wa_secret(stored))


# The stored form of a product key. Plain sha256, matching
# ``routes_whatsapp._hash_key`` byte for byte — the minting side and the
# checking side must agree or every key is dead on arrival. Deliberately not a
# slow KDF: this runs on every product request and a 256-bit random key has no
# dictionary to defend against.
def _hash_api_key(raw: str) -> str:
    return hashlib.sha256(str(raw).encode("utf-8")).hexdigest()


def _api_key_prefix(raw: str) -> str:
    """The non-secret display label for a key: ``qcp_`` + 8 hex of its digest.

    Note that this is **not** a prefix of the key, despite the name of the
    column it lands in (``whatsapp_products.api_key_prefix``, 12 characters).
    Showing the real first characters of a credential is exactly the "just
    the first few characters" disclosure this module refuses everywhere else;
    a digest fragment identifies the key just as well for an operator matching
    the console against a product's environment, and discloses nothing.
    """
    return f"qcp_{_hash_api_key(raw)[:8]}"


def _mint_api_key() -> tuple[str, str, str]:
    """Generate one product key: ``(plaintext, sha256, display prefix)``.

    32 bytes of ``secrets`` entropy. The caller stores the second and third
    and returns the first to the operator exactly once; nothing logs it and
    nothing can recover it afterwards. A lost key is rotated, never retrieved.
    """
    raw = f"qcp_{secrets.token_urlsafe(32)}"
    return raw, _hash_api_key(raw), _api_key_prefix(raw)


# ---------------------------------------------------------------------------
# Account credential descriptors
# ---------------------------------------------------------------------------

# (request field, model column, label, encrypted-at-rest)
#
# All six are required before an account may be switched on. That is stricter
# than ``_account_out["configured"]``, which only asks whether the account
# could address the Graph API: a number that can send but whose app secret is
# missing cannot verify a webhook signature, and one with no verify token
# cannot complete Meta's subscription handshake, so it silently receives
# nothing. "Live" and "can technically POST a message" are not the same state
# and the enable gate uses the stronger one.
_CREDENTIAL_FIELDS: tuple[tuple[str, str, str, bool], ...] = (
    ("access_token", "access_token_encrypted", "Access token", True),
    ("app_secret", "app_secret_encrypted", "App secret", True),
    ("webhook_verify_token", "webhook_verify_token_encrypted", "Webhook verify token", True),
    ("phone_number_id", "phone_number_id", "Phone number ID", False),
    ("waba_id", "waba_id", "WhatsApp Business Account ID", False),
    ("display_phone", "display_phone", "Display phone number", False),
)

# What a connection test genuinely needs. Narrower than the enable gate on
# purpose: an operator should be able to check a token against Meta *before*
# wiring up the webhook half, which is the order the Meta console leads you
# through.
_TEST_CONNECTION_FIELDS = ("access_token", "phone_number_id")


def _plaintext_credential(row: WhatsAppAccount, field: str) -> Optional[str]:
    """The current value of one credential, for fingerprinting only.

    Never returned, never logged, never persisted anywhere by this function's
    callers — the only things derived from it are a length and a digest.
    """
    for name, column, _label, encrypted in _CREDENTIAL_FIELDS:
        if name != field:
            continue
        stored = getattr(row, column, None)
        return wa_credentials.decrypt_wa_secret(stored) if encrypted else (stored or None)
    return None


def _credential_states(row: WhatsAppAccount) -> list[CredentialStateOut]:
    states = []
    for name, _column, label, _encrypted in _CREDENTIAL_FIELDS:
        plain = _plaintext_credential(row, name)
        states.append(
            CredentialStateOut(
                field=name,
                label=label,
                configured=bool(plain),
                length=len(plain) if plain else 0,
                fingerprint=_fingerprint(plain),
                required_to_enable=True,
            )
        )
    return states


def _blocking(row: WhatsAppAccount) -> list[str]:
    """Credential fields still missing before ``enable`` will be accepted."""
    return [
        name
        for name, _column, _label, _encrypted in _CREDENTIAL_FIELDS
        if not _plaintext_credential(row, name)
    ]


def _account_security(row: WhatsAppAccount) -> list[SecurityWarningOut]:
    """Configuration states that are a security posture, not a blank field.

    The first one is the whole reason this list is typed. While
    ``phone_number_id`` is the seeded empty string, the webhook skips
    cross-number attribution entirely — there is no id to compare an envelope
    against — and the two numbers normally share one Meta app, hence one app
    secret. A correctly signed QUATA envelope is therefore accepted at the
    Quata Verify webhook, which is the separation this platform exists to
    enforce, defeated by an empty string in a form nobody finished. That is a
    ``critical``, and the console is handed it as one rather than being left
    to infer severity from an empty field.
    """
    warnings: list[SecurityWarningOut] = []
    if not row.phone_number_id:
        warnings.append(
            SecurityWarningOut(
                code="phone_number_id_unset_webhook_attribution_skipped",
                severity="critical",
                message=(
                    "No phone number ID is set, so the webhook cannot tell an "
                    "envelope for this number from an envelope for the other "
                    "one. Both numbers normally share a Meta app and therefore "
                    "an app secret, so a correctly signed payload for the other "
                    "number would be accepted here. This is a security state, "
                    "not an incomplete form."
                ),
            )
        )
    if not row.app_secret_encrypted:
        warnings.append(
            SecurityWarningOut(
                code="app_secret_unset_webhook_unverifiable",
                severity="warning",
                message=(
                    "No app secret is stored, so no inbound webhook payload for "
                    "this number can have its signature verified. Meta traffic "
                    "will be rejected rather than trusted."
                ),
            )
        )
    if row.is_active and _blocking(row):
        warnings.append(
            SecurityWarningOut(
                code="active_but_incompletely_configured",
                severity="critical",
                message=(
                    "This number is switched on while still missing "
                    f"{', '.join(_blocking(row))}. It was not enabled through "
                    "this API."
                ),
            )
        )
    return warnings


def _account_admin_out(row: WhatsAppAccount) -> AccountAdminOut:
    """The write surface's view of a number. Presence, length, digest only."""
    return AccountAdminOut(
        slug=row.slug,
        name=row.name,
        purpose=row.purpose,
        display_phone=row.display_phone or None,
        api_version=row.api_version,
        is_active=row.is_active,
        health=row.health,
        quality_rating=row.quality_rating,
        messaging_limit=row.messaging_limit,
        last_checked_at=row.last_checked_at,
        last_error=row.last_error,
        configured=bool(
            row.phone_number_id and row.waba_id and row.access_token_encrypted
        ),
        credentials=_credential_states(row),
        blocking=_blocking(row),
        security=_account_security(row),
        webhook_cross_number_attribution=bool(row.phone_number_id),
    )


def _product_admin_out(row: WhatsAppProduct) -> ProductAdminOut:
    purposes = [str(p) for p in (row.allowed_purposes or [])]
    return ProductAdminOut(
        slug=row.slug,
        name=row.name,
        description=row.description,
        is_enabled=row.is_enabled,
        allowed_purposes=purposes,
        default_locale=row.default_locale,
        rate_limit_per_minute=row.rate_limit_per_minute,
        # An empty api_key_hash is an explicit denial at the gateway: no
        # sha256 hex digest can equal "", so a keyless product cannot
        # authenticate, whatever it presents.
        has_api_key=bool(row.api_key_hash),
        api_key_prefix=row.api_key_prefix or None,
        api_key_fingerprint=row.api_key_hash[:12] if row.api_key_hash else None,
        may_reach_authentication=PURPOSE_AUTHENTICATION in purposes,
        last_seen_at=row.last_seen_at,
        created_at=row.created_at,
    )


# ---------------------------------------------------------------------------
# Audit helpers
# ---------------------------------------------------------------------------

def _record(
    db: Session,
    request: Request,
    user: User,
    *,
    action: str,
    resource_type: str,
    resource_id,
    outcome: str = audit.OUTCOME_OK,
    reason: Optional[str] = None,
    details: Optional[dict] = None,
    account_id: Optional[int] = None,
    product_id: Optional[int] = None,
) -> None:
    """One audit row with the human attached.

    ``whatsapp_audit_log`` exists precisely because ``activity_logs`` cannot
    record a machine-initiated denial with no actor. The rows written from
    here are the opposite case and always carry one, plus the caller's address
    as ``get_client_ip`` resolves it.
    """
    audit.record(
        db,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=outcome,
        reason=reason,
        actor_id=user.id,
        account_id=account_id,
        product_id=product_id,
        details=details,
        ip_address=get_client_ip(request),
    )


def _deny(
    db: Session,
    request: Request,
    user: User,
    *,
    action: str,
    resource_type: str,
    resource_id,
    reason: str,
    detail: dict,
    account_id: Optional[int] = None,
    product_id: Optional[int] = None,
    http_status: int = status.HTTP_409_CONFLICT,
) -> None:
    """Refuse a write, on the record, with something a human can act on.

    Always raises. ``detail`` becomes the response body's ``detail`` object
    and always carries a stable ``reason`` code plus a ``message`` in English;
    routes add the specific obstacle (which account is already active, which
    product already owns the thread) so the operator's next step is obvious
    rather than "try something else".
    """
    _record(
        db,
        request,
        user,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=audit.OUTCOME_DENIED,
        reason=reason,
        details={k: v for k, v in detail.items() if k != "message"},
        account_id=account_id,
        product_id=product_id,
    )
    db.commit()
    raise HTTPException(http_status, detail)


def _account_or_404(db: Session, slug: str) -> WhatsAppAccount:
    row = db.query(WhatsAppAccount).filter(WhatsAppAccount.slug == slug).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Account not found")
    return row


def _product_or_404(db: Session, slug: str) -> WhatsAppProduct:
    row = db.query(WhatsAppProduct).filter(WhatsAppProduct.slug == slug).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    return row


# ---------------------------------------------------------------------------
# Accounts — credentials
# ---------------------------------------------------------------------------

@router.put("/admin/qcp/accounts/{slug}/credentials", response_model=AccountAdminOut)
def qcp_set_account_credentials(
    slug: str,
    payload: AccountCredentialsIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM)),
):
    """Store this number's Meta credentials. Never switches it on.

    Only the fields present in the request body are written, so rotating one
    token does not require re-pasting the other five. The three secrets are
    Fernet-encrypted by ``services.whatsapp.credentials`` before they touch a
    column; the three Meta identifiers are not secrets and are stored as
    given, but are still reported back by presence and digest only, because
    ``phone_number_id`` and ``waba_id`` are exactly the values that let
    someone else's traffic be pointed at our number.

    ``purpose`` is deliberately not settable here — or anywhere. It is the
    column the entire authentication/engagement separation travels through
    (composite FKs from ``whatsapp_templates`` and ``whatsapp_messages`` land
    on ``(id, purpose)``), and a number that changed purpose under live
    templates would strand every one of them. ``extra="forbid"`` on the input
    model turns an attempt into a 422 rather than a silent no-op.
    """
    row = _account_or_404(db, slug)
    supplied = payload.model_dump(exclude_unset=True)

    changed: list[dict] = []
    for name, column, _label, encrypted in _CREDENTIAL_FIELDS:
        if name not in supplied or supplied[name] is None:
            continue
        value = str(supplied[name]).strip()
        before = _fingerprint(_plaintext_credential(row, name))
        setattr(row, column, wa_credentials.encrypt_wa_secret(value) if encrypted else value)
        after = _fingerprint(value)
        if before != after:
            # Names as *values*, digests as values: the audit row describes
            # the change and can never hold the credential.
            changed.append({"field": name, "from": before, "to": after})

    if "api_version" in supplied and supplied["api_version"]:
        before = row.api_version
        row.api_version = str(supplied["api_version"]).strip()
        if before != row.api_version:
            changed.append({"field": "api_version", "from": before, "to": row.api_version})

    _record(
        db,
        request,
        user,
        action="account.credentials_set",
        resource_type="whatsapp_account",
        resource_id=row.slug,
        account_id=row.id,
        details={"changed": changed, "purpose": row.purpose},
    )
    db.commit()
    db.refresh(row)
    return _account_admin_out(row)


# ---------------------------------------------------------------------------
# Accounts — the switch
# ---------------------------------------------------------------------------

@router.post("/admin/qcp/accounts/{slug}/enable", response_model=AccountAdminOut)
def qcp_enable_account(
    slug: str,
    payload: AccountEnableIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_OPERATE)),
):
    """Switch a WhatsApp number on. The most consequential action in QCP.

    This is what lets the platform address Meta at all, so it is the only
    route that asks the operator to type the account's own slug back and to
    say why; both land in the audit row, which is what makes "who turned
    Quata Verify on, and what for" answerable months later.

    Three refusals, all audited, none of them a 500:

    * the confirmation does not match the account being enabled;
    * the account is not fully configured — the response names the missing
      fields, because "invalid" is not an instruction;
    * another number of the same purpose is already live. The partial unique
      index ``uq_whatsapp_accounts_active_purpose`` would refuse the INSERT
      anyway; this checks first so the answer names the incumbent, and the
      ``IntegrityError`` handler below still catches the race between two
      operators doing this at once.
    """
    row = _account_or_404(db, slug)

    if payload.confirm_slug.strip() != row.slug:
        _deny(
            db,
            request,
            user,
            action="account.enable_denied",
            resource_type="whatsapp_account",
            resource_id=row.slug,
            account_id=row.id,
            reason="confirmation_mismatch",
            detail={
                "reason": "confirmation_mismatch",
                "message": (
                    f"Type '{row.slug}' to confirm you are switching on this "
                    "number."
                ),
            },
        )

    blocking = _blocking(row)
    if blocking:
        _deny(
            db,
            request,
            user,
            action="account.enable_denied",
            resource_type="whatsapp_account",
            resource_id=row.slug,
            account_id=row.id,
            reason="not_configured",
            detail={
                "reason": "not_configured",
                "blocking": blocking,
                "message": (
                    "This number is not fully configured. Set "
                    f"{', '.join(blocking)} before switching it on."
                ),
            },
        )

    conflict = (
        db.query(WhatsAppAccount)
        .filter(
            WhatsAppAccount.purpose == row.purpose,
            WhatsAppAccount.is_active.is_(True),
            WhatsAppAccount.id != row.id,
        )
        .first()
    )
    if conflict is not None:
        _deny(
            db,
            request,
            user,
            action="account.enable_denied",
            resource_type="whatsapp_account",
            resource_id=row.slug,
            account_id=row.id,
            reason="another_account_active_for_purpose",
            detail={
                "reason": "another_account_active_for_purpose",
                "conflict": conflict.slug,
                "purpose": row.purpose,
                "message": (
                    f"'{conflict.slug}' is already the live {row.purpose} "
                    "number. Switch it off first — only one number per purpose "
                    "may be active."
                ),
            },
        )

    row.is_active = True
    _record(
        db,
        request,
        user,
        action="account.enabled",
        resource_type="whatsapp_account",
        resource_id=row.slug,
        account_id=row.id,
        details={
            "purpose": row.purpose,
            "justification": payload.justification.strip(),
            "display_phone": row.display_phone or None,
        },
    )
    try:
        db.commit()
    except IntegrityError:
        # Lost the race to another operator enabling the sibling number.
        db.rollback()
        _deny(
            db,
            request,
            user,
            action="account.enable_denied",
            resource_type="whatsapp_account",
            resource_id=row.slug,
            account_id=row.id,
            reason="another_account_active_for_purpose",
            detail={
                "reason": "another_account_active_for_purpose",
                "purpose": row.purpose,
                "message": (
                    "Another number of this purpose was switched on at the same "
                    "moment. Only one may be active; reload and try again."
                ),
            },
        )
    db.refresh(row)
    return _account_admin_out(row)


@router.post("/admin/qcp/accounts/{slug}/disable", response_model=AccountAdminOut)
def qcp_disable_account(
    slug: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_OPERATE)),
):
    """Take a number out of service. The safe direction, so no ceremony.

    On ``PERM_OPERATE`` with its dangerous twin even though switching a number
    *off* harms nobody's security: switching off the Quata Verify number stops
    every WhatsApp login code in the fleet, and QuataFood's login has no email
    fallback. It is an availability action of exactly the same size as the
    one above it, and whoever may take the number down is whoever may put it
    back.

    Credentials are deliberately left in place: a number switched off during
    an incident should come back with one click, and deleting the token would
    turn a five-second reversal into a fresh trip to the Meta console.
    """
    row = _account_or_404(db, slug)
    was_active = row.is_active
    row.is_active = False
    _record(
        db,
        request,
        user,
        action="account.disabled",
        resource_type="whatsapp_account",
        resource_id=row.slug,
        account_id=row.id,
        details={"purpose": row.purpose, "was_active": was_active},
    )
    db.commit()
    db.refresh(row)
    return _account_admin_out(row)


@router.post("/admin/qcp/accounts/{slug}/test-connection", response_model=ConnectionTestOut)
def qcp_test_account_connection(
    slug: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM)),
):
    """Ask Meta whether this number is healthy. Messages nobody.

    Reads ``quality_rating`` and the messaging tier off the phone number and
    writes them back onto the account row. It cannot send: the transport's
    only send entry points take a ``SendTicket``, which only
    ``routing.resolve_route`` can mint, and this path never asks for one.
    ``ConnectionTestOut.sent_message`` is pinned ``False`` in the contract so
    the console can say so on the button.

    Refused before any socket opens when the account has no token or no phone
    number id — there is nothing to ask with, and a failed call still costs a
    round trip and an entry in Meta's own logs.
    """
    row = _account_or_404(db, slug)
    missing = [f for f in _TEST_CONNECTION_FIELDS if not _plaintext_credential(row, f)]
    if missing:
        _deny(
            db,
            request,
            user,
            action="account.test_connection_denied",
            resource_type="whatsapp_account",
            resource_id=row.slug,
            account_id=row.id,
            reason="not_configured",
            detail={
                "reason": "not_configured",
                "blocking": missing,
                "message": (
                    "There is nothing to test with yet. Set "
                    f"{', '.join(missing)} first."
                ),
            },
        )

    # The documented entry point for provider calls — see the boundary test in
    # tests/test_whatsapp_boundaries.py. Imported lazily so the console's read
    # routes never drag the delivery path into the process.
    from app.services.whatsapp import dispatch  # noqa: PLC0415

    result = dispatch.fetch_phone_health(db, row, actor_id=user.id)
    _record(
        db,
        request,
        user,
        action="account.test_connection",
        resource_type="whatsapp_account",
        resource_id=row.slug,
        account_id=row.id,
        outcome=audit.OUTCOME_OK if result.get("ok") else audit.OUTCOME_ERROR,
        reason=None if result.get("ok") else str(result.get("error") or "")[:500],
        details={"health": row.health, "purpose": row.purpose},
    )
    db.commit()
    db.refresh(row)
    return ConnectionTestOut(
        account=_account_admin_out(row),
        ok=bool(result.get("ok")),
        health=row.health,
        quality_rating=result.get("quality_rating"),
        messaging_limit=result.get("messaging_limit"),
        verified_name=result.get("verified_name"),
        error=None if result.get("ok") else str(result.get("error") or "")[:400],
    )


# ---------------------------------------------------------------------------
# Products — the plugin registry
# ---------------------------------------------------------------------------

@router.post(
    "/admin/qcp/products",
    response_model=ProductAdminOut,
    status_code=status.HTTP_201_CREATED,
)
def qcp_register_product(
    payload: ProductRegisterIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM)),
):
    """Register a product in the plugin registry — dormant, keyless, capped.

    A new product lands exactly where the seeder leaves the four known ones:
    ``is_enabled=False``, ``api_key_hash=""`` and engagement-only. None of
    those three are accepted from the request body (``extra="forbid"``), so
    registering a product can never be the act that opens an authentication
    path, mints a credential, or starts traffic.
    """
    existing = (
        db.query(WhatsAppProduct).filter(WhatsAppProduct.slug == payload.slug).first()
    )
    if existing is not None:
        _deny(
            db,
            request,
            user,
            action="product.register_denied",
            resource_type="whatsapp_product",
            resource_id=payload.slug,
            product_id=existing.id,
            reason="slug_taken",
            detail={
                "reason": "slug_taken",
                "message": (
                    f"A product with the slug '{payload.slug}' is already "
                    "registered. Slugs are how a product identifies itself at "
                    "the gateway and cannot be reused."
                ),
            },
        )

    row = WhatsAppProduct(
        slug=payload.slug,
        name=payload.name,
        description=payload.description,
        is_enabled=False,
        api_key_hash="",
        api_key_prefix="",
        allowed_purposes=[PURPOSE_ENGAGEMENT],
        default_locale=payload.default_locale,
        rate_limit_per_minute=payload.rate_limit_per_minute,
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        _deny(
            db,
            request,
            user,
            action="product.register_denied",
            resource_type="whatsapp_product",
            resource_id=payload.slug,
            reason="slug_taken",
            detail={
                "reason": "slug_taken",
                "message": (
                    f"A product with the slug '{payload.slug}' was registered at "
                    "the same moment. Slugs cannot be reused."
                ),
            },
        )
    _record(
        db,
        request,
        user,
        action="product.registered",
        resource_type="whatsapp_product",
        resource_id=row.slug,
        product_id=row.id,
        details={"purposes": list(row.allowed_purposes or [])},
    )
    db.commit()
    db.refresh(row)
    return _product_admin_out(row)


class ProductUpdateIn(BaseModel):
    """Correct a registration. Only the three fields a human gets wrong.

    Lives here rather than in ``schemas/whatsapp_admin.py`` only because of
    how this change was split across concurrent editors; it belongs beside
    ``ProductRegisterIn`` and should move there.

    Note what is absent, all of it deliberate and all of it a 422 rather than
    a silent no-op thanks to ``extra="forbid"``:

    * ``slug`` — the identity a product authenticates with at the gateway.
      Renaming it would 401 a live product mid-flight, and every audit row,
      routing rule and template already points at the old one.
    * ``allowed_purposes``, ``is_enabled``, ``api_key_hash`` — the gates.
      Registration refuses them for the same reason: correcting a typo in a
      display name must not be able to open an authentication path or start
      traffic. They have their own routes, their own audit actions, and two
      of the three now need their own permission.
    * ``default_locale`` — not asked for, and not a typo anyone reported.

    ``description`` may be cleared by sending ``null``; ``name`` and
    ``rate_limit_per_minute`` may not, because there is no meaningful empty
    value for either and a cleared cap would read as "unlimited".
    """

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)
    rate_limit_per_minute: Optional[int] = Field(default=None, ge=1, le=100_000)

    @model_validator(mode="after")
    def _at_least_one(self) -> "ProductUpdateIn":
        if not self.model_fields_set:
            raise ValueError("Send at least one field to change.")
        for field in ("name", "rate_limit_per_minute"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be cleared.")
        return self


@router.patch("/admin/qcp/products/{slug}")
def qcp_update_product(
    slug: str,
    payload: ProductUpdateIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM)),
):
    """Correct a product's name, description or rate limit after registration.

    Everything about a registered product used to be whatever was typed into
    the form that created it, for ever. A misspelt name sat on the console and
    in every operator's mental model until someone ran an UPDATE by hand,
    which is precisely the practice this whole write surface exists to end.

    Returns the *registry* shape (``_product_out``), not ``ProductAdminOut``:
    that is the row the products screen already renders, and it is the only
    shape carrying the fields this route edits. Like every other shape here it
    describes a key by presence and prefix and never by value.

    ``rate_limit_per_minute`` gets a second audit row under its own action.
    It is the only field here that is not cosmetic — it caps what a product
    may send — so "who widened QuataFood's throughput, and when" should be one
    query rather than a scan through generic update rows. (Worth knowing while
    reading this: nothing currently *reads* that column. The gateway limits
    every product against the module constant ``routes_whatsapp.QCP_RATE_LIMIT``,
    so today this value is what the console displays, not what the gateway
    enforces. Auditing it costs nothing and is right the moment they are
    joined up.)
    """
    row = _product_or_404(db, slug)
    supplied = payload.model_dump(exclude_unset=True)

    changed: list[dict] = []
    rate_change: Optional[dict] = None
    for field in ("name", "description", "rate_limit_per_minute"):
        if field not in supplied:
            continue
        before = getattr(row, field)
        after = supplied[field]
        if isinstance(after, str):
            after = after.strip() or None
        if field == "name" and not after:
            # ``min_length=1`` already refuses "", but not "   ".
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, "name cannot be blank"
            )
        if before == after:
            continue
        setattr(row, field, after)
        entry = {"field": field, "from": before, "to": after}
        changed.append(entry)
        if field == "rate_limit_per_minute":
            rate_change = entry

    _record(
        db,
        request,
        user,
        action="product.updated",
        resource_type="whatsapp_product",
        resource_id=row.slug,
        product_id=row.id,
        details={"changed": changed},
    )
    if rate_change is not None:
        _record(
            db,
            request,
            user,
            action="product.rate_limit_changed",
            resource_type="whatsapp_product",
            resource_id=row.slug,
            product_id=row.id,
            details={"changed": [rate_change]},
        )
    db.commit()
    db.refresh(row)
    return _product_out(row)


@router.put("/admin/qcp/products/{slug}/purposes", response_model=ProductAdminOut)
def qcp_set_product_purposes(
    slug: str,
    payload: ProductPurposesIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM)),
):
    """Set the ceiling of account purposes a product may ever reach.

    This route may **remove** ``authentication`` but never add it. Adding it
    puts a product's traffic next to the fleet's OTP path, and QuataPay gave
    that path up on 2026-06-03 in favour of email OTP — re-opening it must be
    a deliberate, visible, justified act, not a checkbox that happened to be
    ticked in a form somebody opened to change a rate limit. The dedicated
    route below is where it lives, and the refusal here says so.

    Removing it needs no such ceremony: it is the safe direction. It is still
    audited under its own action, because "when did this product lose its
    auth path" is a question someone will eventually ask.
    """
    row = _product_or_404(db, slug)
    current = {str(p) for p in (row.allowed_purposes or [])}
    requested = set(payload.purposes)

    if PURPOSE_AUTHENTICATION in requested and PURPOSE_AUTHENTICATION not in current:
        _deny(
            db,
            request,
            user,
            action="product.authentication_grant_denied",
            resource_type="whatsapp_product",
            resource_id=row.slug,
            product_id=row.id,
            reason="authentication_grant_requires_dedicated_action",
            detail={
                "reason": "authentication_grant_requires_dedicated_action",
                "message": (
                    "Granting a product access to the authentication number is "
                    "a separate action with a mandatory justification: POST "
                    f"/admin/qcp/products/{row.slug}/purposes/authentication. "
                    "It is not a checkbox on this form."
                ),
            },
        )

    # Canonical order, so two equivalent requests store one value.
    row.allowed_purposes = [
        p for p in (PURPOSE_AUTHENTICATION, PURPOSE_ENGAGEMENT) if p in requested
    ]
    _record(
        db,
        request,
        user,
        action="product.purposes_set",
        resource_type="whatsapp_product",
        resource_id=row.slug,
        product_id=row.id,
        details={
            "changed": [
                {
                    "field": "purposes",
                    "from": sorted(current),
                    "to": list(row.allowed_purposes),
                }
            ]
        },
    )
    # A revoked purpose strands the product's rules for that purpose: still
    # switched on, carrying nothing. They are *named* here rather than
    # deactivated, and that is a deliberate reversal of an earlier proposal.
    #
    # Deactivating them looked tidier and is worse on both counts that matter.
    # (1) It costs diagnosis: with the rule still present ``resolve_route``
    # refuses with ``purpose_not_permitted``, which says what is wrong;
    # deactivate it and the same send refuses with ``no_route``, which does
    # not. ``tests/test_whatsapp_write_surface_attack`` pins the first. (2) It
    # is asymmetric: restoring the grant would not restore the rules, so
    # somebody re-opening QuataFood's login path under pressure would find the
    # grant back and the OTP still dead, with no message saying why.
    #
    # The display problem this was meant to solve is already solved elsewhere:
    # ``registry.blocked_state`` marks such a rule ``is_blocked`` and drops it
    # out of ``is_effectively_live``, so no screen shows it as live. What was
    # missing was the record, which is what this row is.
    revoked = sorted(current - set(row.allowed_purposes))
    if revoked:
        stranded = (
            db.query(WhatsAppRoutingRule)
            .filter(
                WhatsAppRoutingRule.product_id == row.id,
                WhatsAppRoutingRule.purpose.in_(revoked),
                WhatsAppRoutingRule.is_active == True,  # noqa: E712
            )
            .all()
        )
        if stranded:
            _record(
                db,
                request,
                user,
                action="routing_rule.stranded_by_purpose_revoke",
                resource_type="whatsapp_product",
                resource_id=row.slug,
                product_id=row.id,
                outcome=audit.OUTCOME_ERROR,
                reason="purpose_not_permitted",
                details={
                    "purposes_revoked": revoked,
                    "rules": [
                        {"id": r.id, "intent": r.intent, "purpose": r.purpose}
                        for r in stranded
                    ],
                },
            )
    if PURPOSE_AUTHENTICATION in current and PURPOSE_AUTHENTICATION not in requested:
        _record(
            db,
            request,
            user,
            action="product.authentication_revoked",
            resource_type="whatsapp_product",
            resource_id=row.slug,
            product_id=row.id,
            details={"purposes": list(row.allowed_purposes)},
        )
    db.commit()
    db.refresh(row)
    return _product_admin_out(row)


@router.post(
    "/admin/qcp/products/{slug}/purposes/authentication", response_model=ProductAdminOut
)
def qcp_grant_product_authentication(
    slug: str,
    payload: ProductAuthenticationGrantIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_OPERATE)),
):
    """Grant a product the right to reach the Quata Verify number.

    Its own route, its own audit action, and a mandatory justification that is
    stored on the row. The seeded least privilege this defends is specific and
    was arrived at deliberately: QuataFood owns the fleet's only WhatsApp
    authentication path, and QuataPay, Abaqwa and QuataTrade are capped to
    engagement — QuataPay because it moved to email OTP on 2026-06-03. An
    audit answer of "because <blank>" would be worth nothing, so there is no
    way to make one.

    Note the ceiling this raises is *permission*, not routing: the product
    still reaches Verify only through an active ``whatsapp_routing_rules`` row
    resolving to an approved ``authentication`` template on that number.
    """
    row = _product_or_404(db, slug)
    current = [str(p) for p in (row.allowed_purposes or [])]
    if PURPOSE_AUTHENTICATION in current:
        return _product_admin_out(row)

    row.allowed_purposes = [
        p
        for p in (PURPOSE_AUTHENTICATION, PURPOSE_ENGAGEMENT)
        if p == PURPOSE_AUTHENTICATION or p in current
    ]
    _record(
        db,
        request,
        user,
        action="product.authentication_granted",
        resource_type="whatsapp_product",
        resource_id=row.slug,
        product_id=row.id,
        details={
            "justification": payload.justification.strip(),
            "changed": [
                {"field": "purposes", "from": current, "to": list(row.allowed_purposes)}
            ],
        },
    )
    db.commit()
    db.refresh(row)
    return _product_admin_out(row)


# ---------------------------------------------------------------------------
# Products — API keys
# ---------------------------------------------------------------------------

@router.post(
    "/admin/qcp/products/{slug}/api-key",
    response_model=ApiKeyMintedOut,
    status_code=status.HTTP_201_CREATED,
)
def qcp_mint_product_api_key(
    slug: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_OPERATE)),
):
    """Mint (or rotate) this product's gateway key. Shown once, never stored.

    The plaintext exists for the lifetime of this response. What reaches the
    database is ``sha256(key)`` and a display label that is itself a digest
    fragment, so nothing — not this route, not the console, not a later
    request by the same operator — can produce the key again. A lost key is
    rotated, not recovered.

    Minting over an existing key retires the old one immediately: the gateway
    compares against a single stored hash, so the previous key stops
    authenticating on the next request. That is audited as a rotation rather
    than a mint, because "when did this product's key change" is the first
    question asked when a product starts getting 401s.
    """
    row = _product_or_404(db, slug)
    rotating = bool(row.api_key_hash)
    previous_prefix = row.api_key_prefix or None

    plaintext, digest, prefix = _mint_api_key()
    row.api_key_hash = digest
    row.api_key_prefix = prefix

    _record(
        db,
        request,
        user,
        action="product.api_key_rotated" if rotating else "product.api_key_minted",
        resource_type="whatsapp_product",
        resource_id=row.slug,
        product_id=row.id,
        # Prefixes only. Both are digest fragments, so this row identifies the
        # key that changed without ever describing it.
        details={"changed": [{"field": "api_key", "from": previous_prefix, "to": prefix}]},
    )
    db.commit()
    db.refresh(row)
    return ApiKeyMintedOut(
        product=_product_admin_out(row),
        api_key=plaintext,
        prefix=prefix,
        fingerprint=digest[:12],
    )


@router.delete("/admin/qcp/products/{slug}/api-key", response_model=ProductAdminOut)
def qcp_revoke_product_api_key(
    slug: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_OPERATE)),
):
    """Revoke this product's key and stand the product down with it.

    ``api_key_hash`` goes back to ``""``, which is an explicit denial rather
    than an absence: no sha256 hex digest can equal the empty string, so the
    constant-time compare at the gateway fails for every key a caller could
    present, including an empty one.

    The product is disabled in the same transaction. An enabled product with
    no key is a state the console would display as working and the gateway
    would answer 401 to on every call; leaving that behind as the *result* of
    an admin action is how an outage gets misdiagnosed for an afternoon.
    """
    row = _product_or_404(db, slug)
    previous_prefix = row.api_key_prefix or None
    was_enabled = row.is_enabled

    row.api_key_hash = ""
    row.api_key_prefix = ""
    row.is_enabled = False

    _record(
        db,
        request,
        user,
        action="product.api_key_revoked",
        resource_type="whatsapp_product",
        resource_id=row.slug,
        product_id=row.id,
        details={
            "changed": [{"field": "api_key", "from": previous_prefix, "to": None}],
            "was_enabled": was_enabled,
        },
    )
    db.commit()
    db.refresh(row)
    return _product_admin_out(row)


# ---------------------------------------------------------------------------
# Products — the migration gate
# ---------------------------------------------------------------------------

@router.post("/admin/qcp/products/{slug}/enable", response_model=ProductAdminOut)
def qcp_enable_product(
    slug: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM)),
):
    """Migrate a product onto QCP. One product at a time, by hand, on purpose.

    Refused for a product with no key: it could not authenticate at the
    gateway, so "enabled" would be a claim the console makes and every request
    contradicts.

    Note what this does *not* do. It does not activate a number, does not
    touch ``whatsapp.delivery_enabled``, and cannot override
    ``WHATSAPP_ENABLED``. A product enabled while the platform is dormant
    still sends nothing; it is one of four independent gates.
    """
    row = _product_or_404(db, slug)
    if not row.api_key_hash:
        _deny(
            db,
            request,
            user,
            action="product.enable_denied",
            resource_type="whatsapp_product",
            resource_id=row.slug,
            product_id=row.id,
            reason="no_api_key",
            detail={
                "reason": "no_api_key",
                "message": (
                    "This product has no API key, so it cannot authenticate at "
                    "the gateway. Mint one before enabling it."
                ),
            },
        )

    row.is_enabled = True
    _record(
        db,
        request,
        user,
        action="product.enabled",
        resource_type="whatsapp_product",
        resource_id=row.slug,
        product_id=row.id,
        details={"purposes": [str(p) for p in (row.allowed_purposes or [])]},
    )
    db.commit()
    db.refresh(row)
    return _product_admin_out(row)


@router.post("/admin/qcp/products/{slug}/disable", response_model=ProductAdminOut)
def qcp_disable_product(
    slug: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM)),
):
    """Stand a product down. Its key survives, so re-enabling is one click."""
    row = _product_or_404(db, slug)
    was_enabled = row.is_enabled
    row.is_enabled = False
    _record(
        db,
        request,
        user,
        action="product.disabled",
        resource_type="whatsapp_product",
        resource_id=row.slug,
        product_id=row.id,
        details={"was_enabled": was_enabled},
    )
    db.commit()
    db.refresh(row)
    return _product_admin_out(row)


# ---------------------------------------------------------------------------
# Conversations — the unattributed inbound
# ---------------------------------------------------------------------------

@router.post(
    "/admin/qcp/conversations/{conversation_id}/reassign",
    response_model=ConversationReassignOut,
)
def qcp_reassign_conversation(
    conversation_id: int,
    payload: ConversationReassignIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM)),
):
    """Hand an unattributed inbound conversation to a product.

    ``attribute_inbound`` deliberately gives an ambiguous customer reply to
    **nobody** — four products share the QUATA number, ``(account_id,
    wa_contact_id)`` is unique, and every heuristic for guessing the owner
    hands one company's customer to another. It records
    ``conversation.inbound_unattributed`` instead. Until this route existed a
    human could read that denial in the console and had no way to act on it,
    so the customer simply went unanswered. This is the other half of that
    design.

    It is the only path in QCP that sets ``product_id`` on a thread ingest
    left blank, and it never *moves* one: ``adopt_if_unowned`` exists so that
    sending can only ever fill in a blank owner, and a route that could take a
    live thread from the product already working it would reintroduce exactly
    the retroactive loss that model was built to prevent.

    The thread's orphaned inbound messages are handed over with it. Ownership
    of the row and attribution of the messages are separate columns, and
    ``conversations.history`` filters on ``whatsapp_messages.product_id`` — so
    a hand-over that moved only the conversation would give the product an
    empty thread and leave the customer just as unanswered. Only rows with no
    product at all are claimed; a message already carrying another product's
    id is never touched.

    Three audited refusals: the thread already has an owner, the target
    product may not reach that number's purpose, or the product is disabled
    and therefore cannot read what it was just given.
    """
    row = db.get(WhatsAppConversation, conversation_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    product = _product_or_404(db, payload.product)
    account = db.get(WhatsAppAccount, row.account_id)
    purpose = account.purpose if account else None

    if row.product_id is not None:
        owner = db.get(WhatsAppProduct, row.product_id)
        _deny(
            db,
            request,
            user,
            action="conversation.reassign_denied",
            resource_type="whatsapp_conversation",
            resource_id=row.id,
            product_id=product.id,
            account_id=row.account_id,
            reason="already_attributed",
            detail={
                "reason": "already_attributed",
                "conflict": owner.slug if owner else None,
                "message": (
                    "This conversation already belongs to "
                    f"'{owner.slug if owner else 'another product'}'. A thread "
                    "is never taken from the product working it; only an "
                    "unattributed one can be handed over."
                ),
            },
        )

    allowed = [str(p) for p in (product.allowed_purposes or [])]
    if purpose not in allowed:
        _deny(
            db,
            request,
            user,
            action="conversation.reassign_denied",
            resource_type="whatsapp_conversation",
            resource_id=row.id,
            product_id=product.id,
            account_id=row.account_id,
            reason="purpose_not_permitted",
            detail={
                "reason": "purpose_not_permitted",
                "purpose": purpose,
                "product_purposes": allowed,
                "message": (
                    f"'{product.slug}' may not reach the {purpose} number, so it "
                    "cannot be given a conversation on it. Grant the purpose "
                    "first if that is genuinely intended."
                ),
            },
        )

    if not product.is_enabled:
        _deny(
            db,
            request,
            user,
            action="conversation.reassign_denied",
            resource_type="whatsapp_conversation",
            resource_id=row.id,
            product_id=product.id,
            account_id=row.account_id,
            reason="product_disabled",
            detail={
                "reason": "product_disabled",
                "message": (
                    f"'{product.slug}' is not enabled on QCP and cannot read the "
                    "thread, so handing it over would leave the customer just as "
                    "unanswered. Enable the product first."
                ),
            },
        )

    row.product_id = product.id
    claimed = (
        db.query(WhatsAppMessage)
        .filter(
            WhatsAppMessage.conversation_id == row.id,
            WhatsAppMessage.product_id.is_(None),
            WhatsAppMessage.direction == "inbound",
        )
        .update({WhatsAppMessage.product_id: product.id}, synchronize_session=False)
    )

    _record(
        db,
        request,
        user,
        action="conversation.reassigned",
        resource_type="whatsapp_conversation",
        resource_id=row.id,
        product_id=product.id,
        account_id=row.account_id,
        details={
            "product": product.slug,
            "purpose": purpose,
            "messages_attributed": claimed,
            "reason": (payload.reason or "").strip() or None,
        },
    )
    db.commit()
    db.refresh(row)
    return ConversationReassignOut(
        conversation_id=row.id,
        product=product.slug,
        account=account.slug if account else "",
        account_purpose=purpose or "",
        messages_attributed=int(claimed or 0),
        state=row.state,
    )
