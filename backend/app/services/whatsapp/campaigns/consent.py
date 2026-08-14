"""Opt-out: the one thing a campaign platform has to get right.

Meta restricts a number that generates block reports, and QCP has exactly two
numbers — one of which carries the login code for every product in the fleet.
A customer who is messaged after asking to stop does not file a complaint
against "the campaign"; they block **the number**, and the blast radius of
that is QuataFood's phone-change verification, QuataPay's PIN reset, and
every OTP behind them. So opting out is treated as the highest-priority
signal in this package, not as a preference.

**One step, in the customer's own words.** The customer replies ``STOP`` —
or ``ARRÊT``, ``DÉSABONNER``, ``UNSUBSCRIBE`` — to the message they just
received. That is the whole flow. Cameroon is francophone *and* anglophone
and QCP already answers in both (``handover.SUPPORTED_LANGUAGES``), so both
vocabularies are first-class here; an English-only keyword list would mean a
francophone customer who typed the obvious word was messaged again.

**Matching is exact, and that is deliberate.** The normalised message must
*be* a stop word, not contain one. "Please don't stop sending me offers" is
not an opt-out, and a substring rule would read it as one — which produces
the opposite failure: an audience that silently shrinks for reasons nobody
can explain. Meta's own keyword handling works the same way.

**The reply is honoured whether or not anything is listening.** ``sweep``
reads inbound messages QCP has already stored and records every opt-out it
finds; the campaign runner calls it before every batch, so a STOP typed
during a send is honoured within one batch even though nothing in the webhook
path knows this module exists. See ``sweep`` for the one-line hook that would
make it instantaneous instead — that hook is a reported delta, not an edit,
and this module is designed to be correct without it.

**Nothing here deletes an opt-out.** There is no ``forget`` and no admin
route that clears one. Re-consent is a real thing, but it is consent the
customer gives on a channel QCP does not own, and a console button that
quietly re-enrols someone is precisely how a platform earns a Meta
restriction. If it is ever needed it should arrive as its own audited,
evidence-carrying flow.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import WhatsAppMessage

from .. import audit
from .models import OPT_OUT_ADMIN, OPT_OUT_INBOUND, OPT_OUT_SOURCES, WhatsAppOptOut


# English. ``stop`` is Meta's own convention and is what the footer of a
# marketing template is expected to tell people to send.
_STOP_EN = (
    "stop",
    "stop all",
    "unsubscribe",
    "opt out",
    "optout",
    "remove me",
    "cancel",
    "quit",
    "end",
)

# French. ``arret``/``arrêt`` and ``desabonner``/``désabonner`` are the words
# a Douala or Bamenda customer actually types; accents are stripped by
# ``normalise`` so both spellings land on the same entry.
_STOP_FR = (
    "arret",
    "arreter",
    "stop tout",
    "desabonner",
    "me desabonner",
    "se desabonner",
    "desabonnement",
    "annuler",
    "supprimer",
    "ne plus recevoir",
)

STOP_WORDS = frozenset(_STOP_EN + _STOP_FR)

_PUNCTUATION = re.compile(r"[^a-z0-9\s]+")
_WHITESPACE = re.compile(r"\s+")

# How far back ``sweep`` looks when it is given no explicit window. Long
# enough that a campaign paused overnight still honours a reply typed while it
# was paused; bounded so the scan never walks the whole message log.
DEFAULT_SWEEP_DAYS = 30


def _now() -> datetime:
    return datetime.now(timezone.utc)


def normalise(text: Optional[str]) -> str:
    """Lowercase, de-accent, drop punctuation, collapse whitespace.

    ``"ARRÊT!"`` and ``" arret "`` both become ``"arret"``. Accent stripping
    is what lets one entry cover the accented and unaccented spellings of the
    same French word — customers type both, and phone keyboards disagree
    about which they offer.
    """
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", str(text))
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    lowered = _PUNCTUATION.sub(" ", stripped.lower())
    return _WHITESPACE.sub(" ", lowered).strip()


def matched_stop_word(text: Optional[str]) -> Optional[str]:
    """The stop word this message *is*, or None.

    Exact match on the normalised text. See the module docstring for why this
    is not a substring search.
    """
    normalised = normalise(text)
    if not normalised:
        return None
    return normalised if normalised in STOP_WORDS else None


def is_opted_out(db: Session, phone_e164: str) -> bool:
    """The check the runner makes immediately before every single send."""
    if not phone_e164:
        return False
    return (
        db.query(WhatsAppOptOut.id)
        .filter(WhatsAppOptOut.phone_e164 == phone_e164)
        .first()
        is not None
    )


def opted_out_among(db: Session, phones: Iterable[str]) -> set[str]:
    """Which of these numbers have opted out. Used when building an audience.

    Chunked because an audience is allowed to be tens of thousands of rows
    and SQLite caps a statement at 999 bound parameters.
    """
    wanted = [p for p in dict.fromkeys(phones) if p]
    found: set[str] = set()
    for start in range(0, len(wanted), 500):
        chunk = wanted[start : start + 500]
        rows = (
            db.query(WhatsAppOptOut.phone_e164)
            .filter(WhatsAppOptOut.phone_e164.in_(chunk))
            .all()
        )
        found.update(row[0] for row in rows)
    return found


def revoke_queued_campaign_messages(db: Session, phone_e164: str) -> int:
    """Stop every campaign message to this person that has not gone out yet.

    **The last check, and the one that counts.** Opt-out is answered when an
    audience is built, and again when the runner hands a message to
    ``dispatch`` — but a queued message is not a sent message. It waits in
    the outbox for a worker, and a failed one comes back for another attempt
    on a backoff measured in minutes or hours. Somebody who replies STOP in
    that window said stop *before* the message left, and would have received
    it anyway. That is the message that gets reported as spam, and a report
    lands on the **number**, which is how a marketing send ends up restricting
    the login codes for the whole fleet.

    The scope is deliberately narrow. Only outbound rows that carry a
    ``campaign_id`` — a login code is not marketing, and a customer who asked
    the offers to stop did not ask for their own PIN reset to be cancelled —
    and only rows that have not reached the network. ``sending`` is left
    alone: it is claimed by a worker that already holds it, and this module
    does not own the delivery state machine.

    Returns how many were stopped.
    """
    if not phone_e164:
        return 0
    return (
        db.query(WhatsAppMessage)
        .filter(WhatsAppMessage.direction == "outbound")
        .filter(WhatsAppMessage.to_phone_e164 == phone_e164)
        .filter(WhatsAppMessage.campaign_id.isnot(None))
        .filter(WhatsAppMessage.status.in_(("queued", "failed")))
        .update(
            {
                WhatsAppMessage.status: "suppressed",
                WhatsAppMessage.suppressed_reason: "opted_out",
                WhatsAppMessage.next_attempt_at: None,
            },
            synchronize_session=False,
        )
    )


def record(
    db: Session,
    phone_e164: str,
    *,
    source: str,
    evidence: Optional[str] = None,
    note: Optional[str] = None,
    actor_id: Optional[int] = None,
    ip_address: Optional[str] = None,
) -> tuple[Optional[WhatsAppOptOut], bool]:
    """Record one opt-out. Idempotent, audited, never raises on a duplicate.

    Returns ``(row, created)``. A repeat is not an error and not a second row
    — someone who types STOP three times is one person who has said stop.
    """
    phone = (phone_e164 or "").strip()
    if not phone:
        return None, False
    if source not in OPT_OUT_SOURCES:
        source = OPT_OUT_ADMIN

    existing = (
        db.query(WhatsAppOptOut).filter(WhatsAppOptOut.phone_e164 == phone).first()
    )
    if existing is not None:
        return existing, False

    row = WhatsAppOptOut(
        phone_e164=phone[:24],
        source=source,
        evidence=(evidence or None) and str(evidence)[:200],
        note=(note or None) and str(note)[:200],
        actor_id=actor_id,
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError:
        # Lost a race with a concurrent sweep. Their row is as good as ours.
        db.rollback()
        return (
            db.query(WhatsAppOptOut).filter(WhatsAppOptOut.phone_e164 == phone).first(),
            False,
        )

    # Ordered after the flush that could have rolled back, and applied to the
    # outbox before anything else happens: the moment this person is on the
    # list, nothing of ours that is still queued to them may leave.
    revoked = revoke_queued_campaign_messages(db, phone)

    audit.record(
        db,
        action="campaign.opt_out",
        resource_type="whatsapp_opt_out",
        resource_id=phone,
        outcome=audit.OUTCOME_OK,
        reason=source,
        actor_id=actor_id,
        details={"source": source, "evidence": evidence, "revoked": revoked},
        ip_address=ip_address,
    )
    return row, True


def sweep(
    db: Session,
    *,
    since: Optional[datetime] = None,
    limit: int = 500,
) -> dict:
    """Read stored inbound messages and honour every stop word in them.

    This is how a reply becomes an opt-out without anything in the webhook
    path knowing this package exists. ``webhooks._ingest_message`` already
    persists every inbound message with its (redacted) body, and a stop word
    is not a secret, so the evidence is sitting in ``whatsapp_messages`` by
    the time the next batch runs.

    The runner calls this before every batch, so the worst case for a customer
    who replies mid-campaign is one batch — ten seconds at the default pace.
    A one-line call to ``record`` from ``webhooks._ingest_message`` would make
    it instantaneous; that file is outside this change's ownership and the
    call is reported as a delta rather than made here. This function is not a
    stopgap for it — it is also what catches a reply that arrived while the
    campaign was paused, or before the campaign existed at all.

    Returns ``{"scanned", "opted_out", "already"}``.
    """
    window_start = since or (_now() - timedelta(days=DEFAULT_SWEEP_DAYS))
    rows = (
        db.query(WhatsAppMessage)
        .filter(WhatsAppMessage.direction == "inbound")
        .filter(WhatsAppMessage.created_at >= window_start)
        .filter(WhatsAppMessage.from_phone_e164.isnot(None))
        .order_by(WhatsAppMessage.id.desc())
        .limit(max(1, min(limit, 5000)))
        .all()
    )

    created = 0
    already = 0
    for row in rows:
        word = matched_stop_word(row.body)
        if word is None:
            continue
        _, was_new = record(
            db,
            row.from_phone_e164 or "",
            source=OPT_OUT_INBOUND,
            evidence=f"{word} ({row.message_uid})",
        )
        if was_new:
            created += 1
        else:
            already += 1

    return {"scanned": len(rows), "opted_out": created, "already": already}


def recent(db: Session, *, limit: int = 100) -> list[dict]:
    """The opt-out list, newest first, for the console."""
    rows = (
        db.query(WhatsAppOptOut)
        .order_by(WhatsAppOptOut.id.desc())
        .limit(max(1, min(limit, 500)))
        .all()
    )
    return [
        {
            "phone_e164": row.phone_e164,
            "source": row.source,
            "evidence": row.evidence,
            "note": row.note,
            "created_at": row.created_at,
        }
        for row in rows
    ]


def count(db: Session) -> int:
    return db.query(WhatsAppOptOut.id).count()
