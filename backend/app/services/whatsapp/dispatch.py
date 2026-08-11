"""The QCP send path: resolve → persist → hand off → deliver → retry.

    QuataPay · QuataFood · Abaqwa · QuataTrade · (the next one)
                              │
                              ▼
                 send()  ── this module ──►  meta.py ──►  Meta Cloud API
                              │
                              ▼
                    whatsapp_messages (outbox + log)

``send()`` is the single entry point for every product, whether the call is
in-process or an HTTP POST from QuataPay. It is designed to be *safe to call
from a request handler*:

* **it never raises** — a QCP outage must never break a QuataPay checkout,
  the same contract ``notifications.emit`` already holds;
* **it never blocks on Meta** — the row is written, then handed to RQ (when
  Redis is configured) or an in-process thread pool, and the caller returns;
* **it is idempotent** — a repeat POST of the same message returns the
  original ``message_uid`` with ``duplicate: true`` instead of double-sending
  an OTP.

Delivery state lives entirely in ``whatsapp_messages``, so ``sweep_pending``
can recover anything the in-process pool dropped (restart mid-send, pool
saturated, Meta down for an hour), and a message that exhausts
``max_attempts`` lands in ``failed`` — the dead-letter state — where the
admin console and ``dead_letters()`` can see it.

***THIS IS THE ONLY MODULE PERMITTED TO IMPORT ``meta``.*** That is asserted
by ``tests/test_whatsapp_boundaries.py``, not left to convention.

A note on secrets in flight. An OTP is a template *variable*; it has to reach
Meta somehow, so the clear values travel with the hand-off payload (in-process,
or an RQ job body). They are never written to the database in clear — the row
stores ``{"code": "sha256:ab12…"}`` — and never logged. The consequence is
deliberate: after a process restart a queued authentication message cannot be
re-rendered, so the sweeper fails it as ``payload_not_recoverable`` rather
than sending a wrong code. That is what ``routing_rules.fallback_channel``
exists for.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Optional, Sequence

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import WhatsAppAccount, WhatsAppMessage, WhatsAppTemplate

from . import audit, meta, routing, settings_store
from .credentials import decrypt_wa_secret
from .redaction import is_redacted_value, redact_body, redact_variables
from .routing import RoutingDenied, SendTicket


log = logging.getLogger("quata.whatsapp")

STATUS_QUEUED = "queued"
STATUS_SENDING = "sending"
STATUS_SENT = "sent"
STATUS_DELIVERED = "delivered"
STATUS_READ = "read"
STATUS_FAILED = "failed"
STATUS_SUPPRESSED = "suppressed"

TERMINAL_STATUSES = (STATUS_SENT, STATUS_DELIVERED, STATUS_READ, STATUS_SUPPRESSED)

# Five-minute bucket for a derived idempotency key: a retried HTTP call
# seconds apart is a duplicate, a legitimate OTP resend five minutes later
# is a new message.
DEDUPE_WINDOW_SECONDS = 300

_EXECUTOR: Optional[ThreadPoolExecutor] = None


def _executor() -> ThreadPoolExecutor:
    """Lazy in-process fallback worker pool, used when Redis isn't configured.

    Small on purpose: it exists so a request can hand off a send and return,
    not to be a general work queue. Anything it drops is recovered by
    ``sweep_pending``.
    """
    global _EXECUTOR
    if _EXECUTOR is None:
        _EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="quata-whatsapp")
    return _EXECUTOR


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _backoff_seconds(attempts: int) -> int:
    """1m, 2m, 4m, 8m … capped at an hour."""
    return min(60 * (2 ** max(attempts - 1, 0)), 3600)


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

def _derive_idempotency_key(
    *,
    product_slug: str,
    ticket: SendTicket,
    reference: Optional[str],
) -> str:
    variables_digest = hashlib.sha256(
        json.dumps(list(ticket.variables), separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
    ).hexdigest()
    bucket = reference if reference else str(int(time.time()) // DEDUPE_WINDOW_SECONDS)
    basis = "|".join(
        [
            product_slug,
            ticket.account_purpose,
            ticket.to_phone_e164,
            ticket.template_name or "",
            ticket.template_language or "",
            variables_digest,
            bucket,
        ]
    )
    return "auto:" + hashlib.sha256(basis.encode("utf-8")).hexdigest()


def _explicit_idempotency_key(product_slug: str, supplied: str, *, ticket: SendTicket) -> str:
    """Namespace a product-supplied key so a collision cannot cross numbers.

    The product slug alone is not enough, and the failure mode is not
    theoretical: a product that reuses one business reference (``order-7781``)
    across a promotion and a login code got ``{"ok": true, "duplicate": true}``
    for the OTP, pointing at the *marketing* row on the *other* number. No OTP
    row was ever created and the caller was told it succeeded.

    So the account purpose and the recipient are folded in. A supplied key can
    now only collide with a message to the same person, on the same number,
    for the same purpose — which is exactly the retried-POST case the key
    exists to collapse. Intent is deliberately *not* included: a product
    retrying the same OTP request must still dedupe.

    Hashed rather than concatenated because the column is 200 chars and a
    truncated concatenation reintroduces collisions between two long keys that
    share a prefix. ``auto:`` marks a derived key, ``key:`` a supplied one.
    """
    basis = "|".join(
        [product_slug, ticket.account_purpose, ticket.to_phone_e164, supplied]
    )
    return "key:" + hashlib.sha256(basis.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Publish
# ---------------------------------------------------------------------------

def send(
    *,
    product_slug: str,
    intent: str,
    to_phone_e164: str,
    variables: Sequence[str] = (),
    kind: str = "template",
    locale: Optional[str] = None,
    reference: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    body: Optional[str] = None,
    media: Optional[dict] = None,
    source_ip: Optional[str] = None,
    dispatch: bool = True,
) -> dict:
    """Accept one send request. Never raises.

    Returns ``{"ok", "status", "message_uid", "duplicate", "reason"}``.
    ``status`` is the row's status: ``queued`` on a first accept,
    ``suppressed`` when routing refused it. ``duplicate`` is True when the
    idempotency key matched an existing row — the caller should treat that as
    success and *not* retry.
    """
    try:
        return _send_inner(
            product_slug=product_slug,
            intent=intent,
            to_phone_e164=to_phone_e164,
            variables=tuple(str(v) for v in (variables or ())),
            kind=kind,
            locale=locale,
            reference=reference,
            idempotency_key=idempotency_key,
            body=body,
            media=media,
            source_ip=source_ip,
            dispatch=dispatch,
        )
    except Exception as exc:  # noqa: BLE001 — messaging must never break callers
        log.exception(
            "whatsapp.send_failed",
            extra={
                "product": product_slug,
                "intent": intent,
                # A log line is a sink like any other, and the exception may
                # have travelled up from the transport carrying Meta's text.
                "error": meta.scrub_provider_text(str(exc))[:200],
            },
        )
        return {
            "ok": False,
            "status": "error",
            "message_uid": None,
            "duplicate": False,
            "reason": "internal_error",
        }


def _send_inner(
    *,
    product_slug: str,
    intent: str,
    to_phone_e164: str,
    variables: tuple[str, ...],
    kind: str,
    locale: Optional[str],
    reference: Optional[str],
    idempotency_key: Optional[str],
    body: Optional[str],
    media: Optional[dict],
    source_ip: Optional[str],
    dispatch: bool,
) -> dict:
    db = SessionLocal()
    try:
        # 1 ─ the choke point. Nothing else in QCP may mint a SendTicket.
        try:
            ticket = routing.resolve_route(
                db,
                product_slug=product_slug,
                intent=intent,
                to_phone_e164=to_phone_e164,
                kind=kind,
                locale=locale,
                variables=variables,
            )
        except RoutingDenied as denied:
            uid = _record_suppressed(
                db,
                denied,
                product_slug=product_slug,
                to_phone_e164=to_phone_e164,
                variables=variables,
                body=body,
                source_ip=source_ip,
            )
            db.commit()
            log.info(
                "whatsapp.suppressed",
                extra={"product": product_slug, "intent": intent, "reason": denied.reason},
            )
            return {
                "ok": False,
                "status": STATUS_SUPPRESSED,
                "message_uid": uid,
                "duplicate": False,
                "reason": denied.reason,
            }

        # 2 ─ insert-first, then send. The row exists before Meta is touched,
        # so a crash between the two is recoverable rather than invisible.
        key = (
            _explicit_idempotency_key(product_slug, idempotency_key, ticket=ticket)
            if idempotency_key
            else _derive_idempotency_key(
                product_slug=product_slug, ticket=ticket, reference=reference
            )
        )
        row = WhatsAppMessage(
            message_uid=ticket.ticket_id,
            account_id=ticket.account_id,
            account_purpose=ticket.account_purpose,
            product_id=ticket.product_id,
            template_id=ticket.template_id,
            direction="outbound",
            kind=ticket.kind,
            intent=intent[:80],
            to_phone_e164=to_phone_e164[:24],
            body=redact_body(body),
            variables=_variables_for_storage(db, ticket),
            media=media or {},
            idempotency_key=key[:200],
            status=STATUS_QUEUED,
            attempts=0,
            max_attempts=settings_store.max_attempts(),
            next_attempt_at=_now(),
            source_ip=source_ip,
        )
        db.add(row)
        try:
            db.flush()
        except IntegrityError:
            # 3 ─ unique violation on idempotency_key: this exact message is
            # already recorded. Report the original instead of sending twice.
            db.rollback()
            existing = (
                db.query(WhatsAppMessage)
                .filter(WhatsAppMessage.idempotency_key == key[:200])
                .first()
            )
            if existing is None:
                return {
                    "ok": False,
                    "status": "error",
                    "message_uid": None,
                    "duplicate": False,
                    "reason": "insert_conflict",
                }
            log.info(
                "whatsapp.duplicate_suppressed",
                extra={"product": product_slug, "message_uid": existing.message_uid},
            )
            return {
                "ok": True,
                "status": existing.status,
                "message_uid": existing.message_uid,
                "duplicate": True,
                "reason": None,
            }

        audit.record(
            db,
            action="message.accepted",
            resource_type="whatsapp_message",
            resource_id=row.message_uid,
            product_id=ticket.product_id,
            account_id=ticket.account_id,
            details={"intent": intent, "kind": ticket.kind, "purpose": ticket.account_purpose},
            ip_address=source_ip,
        )
        db.commit()
        message_uid = row.message_uid
    finally:
        db.close()

    # 4 ─ hand off. The caller never waits on Meta.
    if dispatch:
        schedule(message_uid, {"variables": list(variables), "body": body})
    return {
        "ok": True,
        "status": STATUS_QUEUED,
        "message_uid": message_uid,
        "duplicate": False,
        "reason": None,
    }


def _redaction_category(
    db: Session,
    *,
    account_purpose: Optional[str],
    template_id: Optional[int],
    resolved: Optional[str] = None,
) -> Optional[str]:
    """The category redaction should assume for a row.

    Authentication is sticky, and unknown resolves *to* authentication:

    * the resolved template's own category decides when we have it;
    * an account whose purpose is ``authentication`` is treated as
      authentication even when the template row cannot be read — the Verify
      number emits nothing but authentication templates;
    * a template id that no longer resolves is treated as authentication too.

    Over-redacting a promotional variable costs a debugging convenience.
    Under-redacting an OTP writes a live login code into the database. The
    asymmetry is the whole design.
    """
    if account_purpose == routing.PURPOSE_AUTHENTICATION:
        return routing.CATEGORY_AUTHENTICATION
    if resolved is not None:
        return resolved
    if template_id is None:
        return None
    template = (
        db.query(WhatsAppTemplate).filter(WhatsAppTemplate.id == template_id).first()
    )
    if template is None:
        return routing.CATEGORY_AUTHENTICATION
    return template.category


def accounts_configured() -> bool:
    """Whether any QCP account holds credentials. Never raises.

    The fact ``Settings.assert_whatsapp_signature_floor(accounts_configured=…)``
    needs at boot, resolved here rather than in ``app/core/config.py``:
    ``app.db.session`` imports the settings module, so a database probe inside
    it would be circular, and configuration has no business reading rows.

    "Configured" means an access token is stored, not that the account is
    active or that delivery is on. Meta posts inbound messages and status
    callbacks to ``POST /whatsapp/webhook/{account_slug}`` regardless of both,
    so an account with credentials is a real number behind an unauthenticated
    door — which is exactly what the boot guard is asking about.

    Any failure answers ``False``: on a fresh box the table may not exist yet,
    and a guard that stops an unmigrated database booting is a worse bug than
    the one it is protecting against. That direction is safe because a
    database with no readable accounts is one nobody has configured.
    """
    try:
        with SessionLocal() as db:
            return (
                db.query(WhatsAppAccount.id)
                .filter(
                    WhatsAppAccount.access_token_encrypted.isnot(None),
                    WhatsAppAccount.access_token_encrypted != "",
                )
                .first()
                is not None
            )
    except Exception as exc:  # noqa: BLE001
        # Type only, deliberately. This is the one place in the module whose
        # exception is a *connection* error, and a driver's connection error
        # text can carry the DSN — which carries the database password.
        log.warning(
            "whatsapp.accounts_probe_failed",
            extra={"error_type": type(exc).__name__},
        )
        return False


def _declared_variable_names(db: Session, template_id: Optional[int]) -> list[str]:
    """The placeholder names a template declares, or ``[]`` when unknowable.

    Redaction needs these on any path that stores variables under ordinals:
    the name an operator gave a placeholder is the only evidence that a
    ``utility`` template is carrying a verification code, and it is discarded
    at exactly the moment the row is written.
    """
    if template_id is None:
        return []
    template = (
        db.query(WhatsAppTemplate).filter(WhatsAppTemplate.id == template_id).first()
    )
    if template is None:
        return []
    return [str(n) for n in (template.variables or [])]


def _variables_for_storage(db: Session, ticket: SendTicket) -> dict:
    """Name the positional variables, then redact them for the row.

    An OTP is stored as ``{"1": "sha256:ab12…"}`` — the same code always
    hashes the same way, so support can compare what a customer quotes
    against the row without the row ever holding the code.

    The names below are cosmetic and frequently positional: Meta's
    authentication templates declare ``{{1}}``, and this falls back to
    positional names whenever the template declares none or declares a
    different number than the caller supplied. So the names are *not* what
    decides redaction — ``ticket.template_category`` is.

    The declared names are handed over separately all the same. Where storage
    falls back to ordinals they are the only record of what the operator
    called each placeholder, and a rule matched against ``"1"`` matches
    nothing. ``ticket.intent`` goes with them: it is what the product asked
    for, and unlike ``category`` no admin form can edit it.
    """
    declared = _declared_variable_names(db, ticket.template_id)
    names = declared
    if len(names) != len(ticket.variables):
        names = [str(i + 1) for i in range(len(ticket.variables))]
    return redact_variables(
        dict(zip(names, ticket.variables)),
        template_category=_redaction_category(
            db,
            account_purpose=ticket.account_purpose,
            template_id=ticket.template_id,
            resolved=ticket.template_category,
        ),
        intent=ticket.intent,
        declared_names=declared,
    )


def _record_suppressed(
    db: Session,
    denied: RoutingDenied,
    *,
    product_slug: str,
    to_phone_e164: str,
    variables: tuple[str, ...],
    body: Optional[str],
    source_ip: Optional[str],
) -> Optional[str]:
    """Write the fullest ``suppressed`` row the CHECK constraints will accept.

    The audit row is written by ``resolve_route`` and is always present — it
    is the record that cannot fail. A *message* row additionally requires a
    resolved account, and the schema's own rules then apply: a template kind
    needs a template id, and the Verify number accepts no outbound row that
    is not a template. When the denial happened before that much was known
    (``product_disabled``, ``no_route``, ``no_account_for_purpose``) there is
    no legal message row to write and the audit row stands alone.

    This is the path that matters most for redaction, because it is the
    *default*: routing check 8 (``delivery_disabled``) is deliberately last,
    and QCP ships dormant, so ``suppressed`` is the outcome of every send
    until an operator flips both gates. The variable names written here are
    always positional — the denial can predate template resolution — so the
    template's declared names are passed to redaction alongside them. Without
    that, a name-based rule on this path has only ordinals to match, which is
    how a verification code on a mis-categorised utility template reached the
    database in clear.
    """
    kind = denied.kind or "template"
    if not denied.account_id or not denied.account_purpose:
        return None
    if kind == "template" and denied.template_id is None:
        return None
    if denied.account_purpose == routing.PURPOSE_AUTHENTICATION and kind != "template":
        return None

    row = WhatsAppMessage(
        message_uid=uuid.uuid4().hex,
        account_id=denied.account_id,
        account_purpose=denied.account_purpose,
        product_id=denied.product_id,
        template_id=denied.template_id,
        direction="outbound",
        kind=kind,
        intent=(denied.intent or "")[:80] or None,
        to_phone_e164=to_phone_e164[:24],
        body=redact_body(body),
        variables=redact_variables(
            {str(i + 1): v for i, v in enumerate(variables)},
            template_category=_redaction_category(
                db,
                account_purpose=denied.account_purpose,
                template_id=denied.template_id,
            ),
            intent=denied.intent,
            declared_names=_declared_variable_names(db, denied.template_id),
        ),
        status=STATUS_SUPPRESSED,
        attempts=0,
        max_attempts=settings_store.max_attempts(),
        next_attempt_at=None,
        suppressed_reason=denied.reason[:200],
        source_ip=source_ip,
    )
    db.add(row)
    db.flush()
    return row.message_uid


# ---------------------------------------------------------------------------
# Async hand-off
# ---------------------------------------------------------------------------

# How long a WhatsApp job — and therefore the clear OTP in its arguments —
# may exist in Redis. Five minutes is longer than any delivery attempt and
# shorter than a login code stays valid, so an undelivered job expires rather
# than sitting in the failed registry with a live code in it. A job that
# expires is not lost: the row is still ``queued`` and ``sweep_pending()``
# re-attempts it, which is also where ``payload_not_recoverable`` fires if
# the code can no longer be re-rendered.
JOB_TTL_SECONDS = 300
# Nothing reads a delivery job's return value; keeping it only keeps the
# job's arguments alive alongside it.
JOB_RESULT_TTL_SECONDS = 0


def schedule(message_uid: str, payload: Optional[dict] = None) -> None:
    """Hand a queued message to a background worker. Never blocks, never raises.

    RQ when ``REDIS_URL`` is configured, an in-process thread otherwise —
    the same two modes ``services/queue.py`` offers, but never synchronous on
    the caller's thread: ``send()`` promises not to block on Meta.

    **``payload`` carries the clear OTP, and on the RQ path that means the
    code is in Redis for the lifetime of the job.** The database row holds
    only a digest; the queue does not. This is a real exposure and it is
    stated here rather than papered over: Redis must be treated as secret
    material, not as scratch space — no public bind, no unauthenticated
    instance, no shared cache instance, and a job TTL short enough that a
    dead job does not outlive the code's own validity. The TTLs below are
    that last part, and they are set here rather than on the shared queue:
    RQ's defaults are ``ttl=None`` (a queued job waits forever),
    ``result_ttl=500`` and ``failure_ttl=31536000``, so a job that *failed*
    would keep its arguments — the clear OTP among them — in Redis for a
    year. ``services/queue.py`` is shared with newsletter and email jobs
    that legitimately want the long failure window, so only WhatsApp's own
    enqueue is narrowed.

    It is *not* fixable by passing a reference instead of the value. The
    reference would have to point at the code, and the only place to put it
    is the row — which is precisely what redaction empties. Storing it
    anywhere retrievable rebuilds the leak this module just closed, and not
    storing it means the worker has nothing to render, i.e. exactly the
    ``payload_not_recoverable`` path. So the value travels with the job, and
    the recoverability rule stands: once the job is gone the message cannot be
    re-rendered and falls back on ``routing_rules.fallback_channel``.
    """
    try:
        from app.services.queue import _get_queue  # noqa: PLC0415

        queue = _get_queue()
    except Exception:  # noqa: BLE001
        queue = None

    if queue is not None:
        try:
            queue.enqueue(
                deliver_message,
                message_uid,
                payload,
                description=f"wa:{message_uid}",
                ttl=JOB_TTL_SECONDS,
                result_ttl=JOB_RESULT_TTL_SECONDS,
                failure_ttl=JOB_TTL_SECONDS,
            )
            return
        except Exception as exc:  # noqa: BLE001 — fall through to threads
            log.warning(
                "whatsapp.enqueue_failed",
                extra={"error": meta.scrub_provider_text(str(exc))[:200]},
            )

    try:
        _executor().submit(deliver_message, message_uid, payload)
    except Exception as exc:  # noqa: BLE001
        # Nothing dispatched now — sweep_pending() will catch it.
        log.warning(
            "whatsapp.submit_failed",
            extra={"error": meta.scrub_provider_text(str(exc))[:200]},
        )


# ---------------------------------------------------------------------------
# Delivery
# ---------------------------------------------------------------------------

def _positional_values(stored: dict, count: int) -> Optional[list]:
    """Read ``{"1": …, "2": …}`` back in order, or None if it isn't that shape.

    ``_record_suppressed`` names variables positionally because a denial can
    happen before any template is resolved, so ordering must be recovered from
    the names rather than from dict insertion order.
    """
    names = [str(i + 1) for i in range(count)]
    if count != len(stored) or not all(n in stored for n in names):
        return None
    return [stored[n] for n in names]


def _recover_payload(db: Session, row: WhatsAppMessage) -> Optional[dict]:
    """Rebuild the send payload from the stored row, or None if impossible.

    Impossible means "the row holds a redaction marker" — an authentication
    template whose code was digested at ingest. Sending the marker would
    deliver a wrong code, so the caller fails the message instead. That rule
    is absolute and is checked first: nothing below can make an OTP
    recoverable.

    Everything after it is *ordering*, and ordering is where this used to
    dead-letter legitimate messages. A row's variable names come from one of
    two places. A ``queued`` row is named by ``_variables_for_storage``, which
    uses the template's declared names when the arity matches. A
    ``suppressed`` row is named by ``_record_suppressed``, which is always
    positional — the denial can predate template resolution. Looking the
    declared names up in a positional dict finds nothing, and QCP ships
    dormant, so *every* row in the backlog is suppressed: the first retry
    after delivery is switched on would have dead-lettered every named
    template in it.
    """
    stored = row.variables or {}
    if any(is_redacted_value(v) for v in stored.values()):
        return None

    names: list[str] = []
    if row.template_id is not None:
        template = (
            db.query(WhatsAppTemplate)
            .filter(WhatsAppTemplate.id == row.template_id)
            .first()
        )
        names = [str(n) for n in ((template.variables if template else None) or [])]

    if names and all(n in stored for n in names):
        values = [stored[n] for n in names]
    else:
        values = _positional_values(stored, len(names) if names else len(stored))
        if values is None:
            # Neither the declared names nor a complete positional set — the
            # order of the variables is unknown and a template rendered in the
            # wrong order is worse than one that falls back.
            if names:
                return None
            values = list(stored.values())

    return {"variables": [str(v) for v in values], "body": row.body}


def deliver_message(message_uid: str, payload: Optional[dict] = None) -> dict:
    """Deliver one queued message. Runs off the request path, owns its session.

    Safe to call concurrently: the row is claimed with a guarded UPDATE, so a
    second worker on the same message is a no-op.
    """
    db = SessionLocal()
    try:
        row = (
            db.query(WhatsAppMessage)
            .filter(WhatsAppMessage.message_uid == message_uid)
            .first()
        )
        if row is None:
            return {"ok": False, "reason": "not_found"}
        if row.status in TERMINAL_STATUSES:
            return {"ok": True, "reason": "already_final", "status": row.status}

        claimed = (
            db.query(WhatsAppMessage)
            .filter(
                WhatsAppMessage.id == row.id,
                WhatsAppMessage.status.in_([STATUS_QUEUED, STATUS_FAILED]),
            )
            .update(
                {
                    WhatsAppMessage.status: STATUS_SENDING,
                    WhatsAppMessage.attempts: WhatsAppMessage.attempts + 1,
                },
                synchronize_session=False,
            )
        )
        db.commit()
        if not claimed:
            return {"ok": False, "reason": "claimed_elsewhere"}
        db.refresh(row)

        if payload is None:
            payload = _recover_payload(db, row)
        if payload is None:
            # An OTP cannot be re-rendered from a digest. Fail it loudly so
            # the product falls back on the channel its routing rule names.
            return _record_failure(
                db, row, "Send payload is not recoverable after a restart.", retryable=False,
                error_code="payload_not_recoverable",
            )

        return _send_row(db, row, payload)
    except Exception as exc:  # noqa: BLE001
        safe = meta.scrub_provider_text(str(exc))[:200]
        log.exception(
            "whatsapp.deliver_failed",
            extra={"message_uid": message_uid, "error": safe},
        )
        return {"ok": False, "reason": "exception", "error": safe}
    finally:
        db.close()


def _send_row(db: Session, row: WhatsAppMessage, payload: dict) -> dict:
    variables = tuple(str(v) for v in (payload.get("variables") or ()))

    # The invariant is crossed a *second* time on the way out: the ticket is
    # rebuilt from the current account and template rows, not from the
    # message row's word.
    try:
        ticket = routing.rebuild_ticket(db, row, variables=variables)
    except RoutingDenied as denied:
        audit.record(
            db,
            action="routing.denied",
            resource_type="whatsapp_message",
            resource_id=row.message_uid,
            outcome=audit.OUTCOME_DENIED,
            reason=denied.reason,
            product_id=row.product_id,
            account_id=row.account_id,
            details={"stage": "delivery"},
        )
        row.status = STATUS_SUPPRESSED
        row.suppressed_reason = denied.reason[:200]
        row.next_attempt_at = None
        db.commit()
        return {"ok": False, "status": STATUS_SUPPRESSED, "reason": denied.reason}

    try:
        if ticket.kind == "template":
            result = meta.send_template(ticket, db=db)
        else:
            result = meta.send_text(ticket, db=db, body_text=str(payload.get("body") or ""))
    except RoutingDenied as denied:
        # L3 refused the ticket. No HTTP was issued.
        audit.record(
            db,
            action="routing.denied",
            resource_type="whatsapp_message",
            resource_id=row.message_uid,
            outcome=audit.OUTCOME_DENIED,
            reason=denied.reason,
            product_id=row.product_id,
            account_id=row.account_id,
            details={"stage": "transport"},
        )
        row.status = STATUS_SUPPRESSED
        row.suppressed_reason = denied.reason[:200]
        row.next_attempt_at = None
        db.commit()
        return {"ok": False, "status": STATUS_SUPPRESSED, "reason": denied.reason}

    if result.ok:
        row.status = STATUS_SENT
        row.provider_message_id = result.provider_message_id
        row.sent_at = _now()
        row.next_attempt_at = None
        row.last_error = None
        row.error_code = None
        audit.record(
            db,
            action="message.sent",
            resource_type="whatsapp_message",
            resource_id=row.message_uid,
            product_id=row.product_id,
            account_id=row.account_id,
            details={"intent": row.intent, "purpose": row.account_purpose},
        )
        db.commit()
        log.info(
            "whatsapp.sent",
            extra={"message_uid": row.message_uid, "purpose": row.account_purpose},
        )
        return {"ok": True, "status": STATUS_SENT, "message_uid": row.message_uid}

    return _record_failure(
        db,
        row,
        result.error or "Delivery failed",
        retryable=result.retryable,
        error_code=result.error_code,
        retry_after=result.retry_after,
    )


def _record_failure(
    db: Session,
    row: WhatsAppMessage,
    error: str,
    *,
    retryable: bool,
    error_code: Optional[str] = None,
    retry_after: Optional[int] = None,
) -> dict:
    """Move a row out of ``sending`` after an unsuccessful attempt.

    A retryable failure goes back to ``queued`` with a backoff. Anything else
    — or an exhausted attempt budget — becomes ``failed``: the dead-letter
    state, terminal until an admin retries it explicitly.

    ``error`` is Meta's own words, and this is where they stop being transient
    and become a row an admin reads. ``meta._failure`` has already removed the
    access token it was holding; that is one shape of one credential, so the
    string is scrubbed again here — by shape, and against every credential
    *this account* stores. Truncation happens after the scrub, never before:
    cutting first can slice a token in half and leave the half that matters.
    """
    account = (
        db.query(WhatsAppAccount).filter(WhatsAppAccount.id == row.account_id).first()
        if row.account_id
        else None
    )
    safe_error = _without_account_secrets(error, account)
    safe_code = meta.scrub_provider_text(str(error_code)) if error_code else None
    row.last_error = safe_error[:500]
    row.error_code = safe_code[:40] if safe_code else None
    exhausted = row.attempts >= row.max_attempts
    if retryable and not exhausted:
        row.status = STATUS_QUEUED
        delay = retry_after if retry_after else _backoff_seconds(row.attempts)
        row.next_attempt_at = _now() + timedelta(seconds=int(delay))
    else:
        row.status = STATUS_FAILED
        row.failed_at = _now()
        row.next_attempt_at = None
        audit.record(
            db,
            action="message.dead_lettered",
            resource_type="whatsapp_message",
            resource_id=row.message_uid,
            outcome=audit.OUTCOME_ERROR,
            reason=row.error_code or "delivery_failed",
            product_id=row.product_id,
            account_id=row.account_id,
            details={"attempts": row.attempts},
        )
    db.commit()
    log.warning(
        "whatsapp.delivery_failed",
        extra={
            "message_uid": row.message_uid,
            "attempts": row.attempts,
            "status": row.status,
            "retryable": retryable,
        },
    )
    return {
        "ok": False,
        "status": row.status,
        "attempts": row.attempts,
        "error": row.last_error,
    }


# ---------------------------------------------------------------------------
# Recovery
# ---------------------------------------------------------------------------

def sweep_pending(limit: int = 100) -> dict:
    """Deliver every message that's due. Called by the QCP worker.

    The safety net: nothing depends on the in-process pool surviving, only on
    this running periodically.
    """
    db = SessionLocal()
    try:
        due = (
            db.query(WhatsAppMessage.message_uid)
            .filter(WhatsAppMessage.status == STATUS_QUEUED)
            .filter(
                (WhatsAppMessage.next_attempt_at.is_(None))
                | (WhatsAppMessage.next_attempt_at <= _now())
            )
            .order_by(WhatsAppMessage.id)
            .limit(limit)
            .all()
        )
        uids = [u[0] for u in due]
    finally:
        db.close()

    sent = 0
    failed = 0
    for uid in uids:
        outcome = deliver_message(uid)
        if outcome.get("ok"):
            sent += 1
        else:
            failed += 1
    return {"picked": len(uids), "sent": sent, "failed": failed}


def reclaim_stuck(older_than_minutes: int = 15) -> int:
    """Return messages wedged in ``sending`` to ``queued``.

    A worker killed mid-send leaves its claim behind; without this the row
    would sit in ``sending`` forever and never retry.
    """
    cutoff = _now() - timedelta(minutes=older_than_minutes)
    db = SessionLocal()
    try:
        count = (
            db.query(WhatsAppMessage)
            .filter(WhatsAppMessage.status == STATUS_SENDING)
            .filter(WhatsAppMessage.updated_at <= cutoff)
            .update(
                {
                    WhatsAppMessage.status: STATUS_QUEUED,
                    WhatsAppMessage.next_attempt_at: _now(),
                },
                synchronize_session=False,
            )
        )
        db.commit()
        if count:
            log.warning("whatsapp.reclaimed_stuck", extra={"count": count})
        return count
    finally:
        db.close()


def retry_message(message_uid: str, *, reset_attempts: bool = True) -> dict:
    """Admin-triggered retry of a failed or suppressed message."""
    db = SessionLocal()
    try:
        row = (
            db.query(WhatsAppMessage)
            .filter(WhatsAppMessage.message_uid == message_uid)
            .first()
        )
        if row is None:
            return {"ok": False, "error": "Message not found"}
        if row.status in (STATUS_SENT, STATUS_DELIVERED, STATUS_READ):
            return {"ok": True, "status": row.status, "note": "Already delivered"}
        if reset_attempts:
            row.attempts = 0
        row.status = STATUS_QUEUED
        row.suppressed_reason = None
        row.next_attempt_at = _now()
        db.commit()
    finally:
        db.close()
    return deliver_message(message_uid)


def dead_letters(db: Session, *, limit: int = 50) -> list[WhatsAppMessage]:
    """Messages that exhausted their attempts or failed permanently."""
    return (
        db.query(WhatsAppMessage)
        .filter(WhatsAppMessage.status == STATUS_FAILED)
        .order_by(WhatsAppMessage.id.desc())
        .limit(limit)
        .all()
    )


def get_message(db: Session, message_uid: str) -> Optional[WhatsAppMessage]:
    return (
        db.query(WhatsAppMessage)
        .filter(WhatsAppMessage.message_uid == message_uid)
        .first()
    )


# ---------------------------------------------------------------------------
# Non-send provider calls — thin audited passthroughs
# ---------------------------------------------------------------------------

def _stored_secrets(account: Optional[WhatsAppAccount]) -> tuple[str, ...]:
    """This account's decrypted credentials, for exact-match scrubbing only.

    Never returned, never logged, never persisted — the values exist for the
    length of one ``scrub_provider_text`` call and are used only to recognise
    themselves inside somebody else's string.
    """
    if account is None:
        return ()
    return tuple(
        secret
        for secret in (
            decrypt_wa_secret(account.access_token_encrypted),
            decrypt_wa_secret(account.app_secret_encrypted),
            decrypt_wa_secret(account.webhook_verify_token_encrypted),
        )
        if secret
    )


def _without_account_secrets(
    text: Optional[str], account: Optional[WhatsAppAccount]
) -> str:
    """Make provider text safe to write down, for a known account.

    Two rules, in that order:

    * **By shape** — ``meta.scrub_provider_text`` removes anything that looks
      like a credential whether or not we hold a copy of it. That is what
      catches an escaped or truncated token, a bearer header, a proof hash, a
      signed URL Meta echoes back, and the token of an account other than this
      one. An exact-match filter catches none of those.
    * **By equality** — then this account's own stored values, which covers the
      **app secret** and the **webhook verify token** that ``meta._scrub``
      never sees, and any credential whose shape we have not anticipated.

    Applied wherever the text stops being transient: ``account.last_error``
    and ``whatsapp_messages.last_error`` are persisted, audited, and rendered
    in the admin console.
    """
    return meta.scrub_provider_text(text, *_stored_secrets(account))


def fetch_message_templates(db: Session, account: WhatsAppAccount) -> dict:
    """Meta's template list for one account. Audited, read-only."""
    result = meta.list_message_templates(account, db=db)
    if result.get("error") is not None:
        result["error"] = _without_account_secrets(result.get("error"), account)
    audit.record(
        db,
        action="template.synced",
        resource_type="whatsapp_account",
        resource_id=str(account.id),
        outcome=audit.OUTCOME_OK if result.get("ok") else audit.OUTCOME_ERROR,
        reason=None if result.get("ok") else str(result.get("error"))[:500],
        account_id=account.id,
        details={"count": len(result.get("data") or [])},
    )
    return result


def fetch_phone_health(
    db: Session, account: WhatsAppAccount, *, actor_id: Optional[int] = None
) -> dict:
    """Quality rating + messaging tier, written back onto the account row.

    ``actor_id`` is optional because the worker calls this on a schedule with
    nobody behind it. When the console calls it, the human is passed through
    so the health-check row is attributable rather than looking machine-made
    next to the ``account.test_connection`` row the route writes.
    """
    result = meta.get_phone_health(account, db=db)
    if result.get("error") is not None:
        result["error"] = _without_account_secrets(result.get("error"), account)
    account.last_checked_at = _now()
    if result.get("ok"):
        account.health = "ok"
        account.quality_rating = (result.get("quality_rating") or None)
        account.messaging_limit = (result.get("messaging_limit") or None)
        account.last_error = None
    else:
        account.health = "unauthorized" if result.get("unauthorized") else "degraded"
        account.last_error = str(result.get("error") or "")[:500]
    audit.record(
        db,
        action="account.health_checked",
        resource_type="whatsapp_account",
        resource_id=str(account.id),
        outcome=audit.OUTCOME_OK if result.get("ok") else audit.OUTCOME_ERROR,
        reason=None if result.get("ok") else account.last_error,
        actor_id=actor_id,
        account_id=account.id,
        details={"health": account.health},
    )
    db.commit()
    return result


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------

def stats(db: Session, *, hours: int = 24) -> dict:
    """Counts for the admin console header."""
    since = _now() - timedelta(hours=hours)
    rows = (
        db.query(WhatsAppMessage.status, func.count(WhatsAppMessage.id))
        .filter(WhatsAppMessage.created_at >= since)
        .group_by(WhatsAppMessage.status)
        .all()
    )
    by_status = {status: count for status, count in rows}
    return {
        "window_hours": hours,
        "delivery_enabled": settings_store.delivery_enabled(),
        "total": sum(by_status.values()),
        "queued": by_status.get(STATUS_QUEUED, 0) + by_status.get(STATUS_SENDING, 0),
        "sent": by_status.get(STATUS_SENT, 0)
        + by_status.get(STATUS_DELIVERED, 0)
        + by_status.get(STATUS_READ, 0),
        "failed": by_status.get(STATUS_FAILED, 0),
        "suppressed": by_status.get(STATUS_SUPPRESSED, 0),
    }
