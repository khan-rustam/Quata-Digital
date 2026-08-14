"""Who a campaign goes to — built only from data QCP already holds.

**There is no customer database here and there must never be one.** QCP is a
messaging backbone; the products own their customers. Inventing a contacts
table would create a second, unsynchronised copy of QuataFood's users that
nobody deletes when a customer closes their account — which is a data
protection problem wearing a marketing feature's clothes.

So an audience is a *query over QCP's own log*, and there are exactly two
sources, both of which are records of a conversation that already happened on
the engagement number:

``conversations``
    Contacts who have a thread with QUATA — that is, people who messaged the
    number. This is the strongest basis QCP has: they initiated.

``product_contacts``
    Addresses a given product has already reached through the gateway. The
    product supplied them, through the path it already uses, for a message it
    already sent. QCP is not learning anything new about them here — it is
    re-reading its own outbox.

Both are scoped to the **engagement** account. Contacts of the Quata Verify
number are not an audience: they are people who received a login code, and
that is the one relationship this platform exists to keep marketing away
from. The scope is expressed as a query filter *and* re-asserted at send
time by routing, so a bug here still cannot put a campaign on Verify.

Opt-outs are removed at build time and checked again immediately before every
individual send. Twice, because the two answers are taken at different
moments and the later one is the one that matters — a customer who says STOP
after the audience is built must not receive the rest of the campaign.

Filters are an allow-list. An unrecognised key is refused rather than
ignored: an operator who mistypes ``inbound_within_day`` and gets the whole
contact list instead of the last month's is the failure mode that makes
"send to the wrong audience" happen.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models import WhatsAppConversation, WhatsAppMessage, WhatsAppProduct

from . import consent


SOURCE_CONVERSATIONS = "conversations"
SOURCE_PRODUCT_CONTACTS = "product_contacts"
SOURCES = (SOURCE_CONVERSATIONS, SOURCE_PRODUCT_CONTACTS)

# Human sentences for the console, kept next to the sources they describe so
# the screen never has to invent an explanation of where a list came from.
SOURCE_LABELS = {
    SOURCE_CONVERSATIONS: "People who have messaged QUATA",
    SOURCE_PRODUCT_CONTACTS: "Addresses this product has already reached through QCP",
}

_FILTERS = {
    SOURCE_CONVERSATIONS: {"state", "inbound_within_days", "locale", "limit"},
    SOURCE_PRODUCT_CONTACTS: {"since_days", "limit"},
}

CONVERSATION_STATES = ("open", "snoozed", "closed")

# A hard ceiling on any one campaign. Not a performance number — a blast
# radius. 50,000 messages at the fastest permitted pace is over thirteen
# hours, which is the point: a campaign is a thing you can watch and stop.
MAX_AUDIENCE = 50_000
DEFAULT_LIMIT = 5_000


class AudienceRefused(Exception):
    """A stated refusal: a stable code and a sentence naming the fix."""

    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True)
class Candidate:
    phone_e164: str
    conversation_id: Optional[int]
    locale: Optional[str]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def validate(source: str, filters: Optional[dict]) -> dict:
    """Check the source and its filters. Returns the cleaned filter dict."""
    if source not in SOURCES:
        raise AudienceRefused(
            "unknown_audience_source",
            f"'{source}' is not an audience QCP can build. Choose one of: "
            f"{', '.join(SOURCES)}.",
        )

    supplied = dict(filters or {})
    allowed = _FILTERS[source]
    unknown = sorted(set(supplied) - allowed)
    if unknown:
        raise AudienceRefused(
            "unknown_audience_filter",
            f"{', '.join(unknown)} is not a filter for the '{source}' audience. "
            f"Allowed: {', '.join(sorted(allowed))}. A filter QCP does not "
            "understand is refused rather than ignored — silently widening an "
            "audience is how the wrong people get messaged.",
        )

    cleaned: dict = {}
    if "state" in supplied and supplied["state"] not in (None, ""):
        state = str(supplied["state"])
        if state not in CONVERSATION_STATES:
            raise AudienceRefused(
                "invalid_conversation_state",
                f"'{state}' is not a conversation state ({', '.join(CONVERSATION_STATES)}).",
            )
        cleaned["state"] = state

    for key in ("inbound_within_days", "since_days"):
        if key in supplied and supplied[key] not in (None, ""):
            try:
                days = int(supplied[key])
            except (TypeError, ValueError) as exc:
                raise AudienceRefused(
                    "invalid_audience_filter", f"{key} must be a whole number of days."
                ) from exc
            if days < 1 or days > 3650:
                raise AudienceRefused(
                    "invalid_audience_filter",
                    f"{key} must be between 1 and 3650 days.",
                )
            cleaned[key] = days

    if "locale" in supplied and supplied["locale"] not in (None, ""):
        cleaned["locale"] = str(supplied["locale"])[:10]

    limit = supplied.get("limit")
    if limit in (None, ""):
        cleaned["limit"] = DEFAULT_LIMIT
    else:
        try:
            value = int(limit)
        except (TypeError, ValueError) as exc:
            raise AudienceRefused(
                "invalid_audience_filter", "limit must be a whole number."
            ) from exc
        if value < 1 or value > MAX_AUDIENCE:
            raise AudienceRefused(
                "audience_too_large",
                f"An audience is capped at {MAX_AUDIENCE:,} recipients. A larger "
                "send should be split so it can be watched and stopped.",
            )
        cleaned["limit"] = value
    return cleaned


def resolve(
    db: Session,
    *,
    source: str,
    filters: Optional[dict],
    account_id: int,
    product: WhatsAppProduct,
) -> list[Candidate]:
    """The eligible audience: deduped, engagement-only, opt-outs removed."""
    cleaned = validate(source, filters)
    limit = cleaned["limit"]

    if source == SOURCE_CONVERSATIONS:
        rows = _from_conversations(db, cleaned, account_id=account_id, limit=limit)
    else:
        rows = _from_product_contacts(
            db, cleaned, account_id=account_id, product_id=product.id, limit=limit
        )

    blocked = consent.opted_out_among(db, [row.phone_e164 for row in rows])
    return [row for row in rows if row.phone_e164 not in blocked]


def preview(
    db: Session,
    *,
    source: str,
    filters: Optional[dict],
    account_id: int,
    product: WhatsAppProduct,
) -> dict:
    """What a build would produce, without writing anything.

    ``matched`` is what the query found; ``eligible`` is what would actually
    be sent to. The gap between them is the opt-out list, reported as its own
    number rather than folded in — an operator who watches an audience shrink
    should be told it was consent that shrank it.
    """
    cleaned = validate(source, filters)
    limit = cleaned["limit"]

    if source == SOURCE_CONVERSATIONS:
        rows = _from_conversations(db, cleaned, account_id=account_id, limit=limit)
    else:
        rows = _from_product_contacts(
            db, cleaned, account_id=account_id, product_id=product.id, limit=limit
        )

    blocked = consent.opted_out_among(db, [row.phone_e164 for row in rows])
    eligible = [row for row in rows if row.phone_e164 not in blocked]
    return {
        "source": source,
        "label": SOURCE_LABELS[source],
        "filters": cleaned,
        "matched": len(rows),
        "opted_out": len(rows) - len(eligible),
        "eligible": len(eligible),
        "capped": len(rows) >= limit,
        "limit": limit,
        # Enough to recognise the shape of the list, not enough to be a
        # contact export. The console shows these as a sanity check.
        "sample": [row.phone_e164 for row in eligible[:10]],
    }


def _from_conversations(
    db: Session, filters: dict, *, account_id: int, limit: int
) -> list[Candidate]:
    query = db.query(WhatsAppConversation).filter(
        WhatsAppConversation.account_id == account_id
    )
    if "state" in filters:
        query = query.filter(WhatsAppConversation.state == filters["state"])
    if "locale" in filters:
        query = query.filter(WhatsAppConversation.locale == filters["locale"])
    if "inbound_within_days" in filters:
        cutoff = _now() - timedelta(days=filters["inbound_within_days"])
        query = query.filter(WhatsAppConversation.last_inbound_at >= cutoff)

    rows = (
        query.order_by(WhatsAppConversation.last_inbound_at.desc().nulls_last())
        .limit(limit)
        .all()
    )
    seen: set[str] = set()
    out: list[Candidate] = []
    for row in rows:
        phone = (row.phone_e164 or "").strip()
        if not phone or phone in seen:
            continue
        seen.add(phone)
        out.append(Candidate(phone_e164=phone, conversation_id=row.id, locale=row.locale))
    return out


def _from_product_contacts(
    db: Session, filters: dict, *, account_id: int, product_id: int, limit: int
) -> list[Candidate]:
    """Addresses this product has already reached, on the engagement number.

    Read off ``whatsapp_messages`` — QCP's own outbox — rather than off any
    list a product uploads. If a product wants somebody in a campaign, the
    way it says so is the way it already says so: send them something through
    the gateway.
    """
    query = (
        db.query(WhatsAppMessage)
        .filter(WhatsAppMessage.product_id == product_id)
        .filter(WhatsAppMessage.account_id == account_id)
        .filter(WhatsAppMessage.direction == "outbound")
        .filter(WhatsAppMessage.to_phone_e164.isnot(None))
    )
    if "since_days" in filters:
        cutoff = _now() - timedelta(days=filters["since_days"])
        query = query.filter(WhatsAppMessage.created_at >= cutoff)

    seen: set[str] = set()
    out: list[Candidate] = []
    # Walked newest-first and deduped in Python rather than with DISTINCT so
    # the row's conversation id travels with the address — the recipient row
    # keeps it, which is what lets the console jump from a campaign result
    # straight into the thread it landed in.
    for row in (
        query.order_by(WhatsAppMessage.id.desc()).limit(max(limit * 4, limit)).all()
    ):
        phone = (row.to_phone_e164 or "").strip()
        if not phone or phone in seen:
            continue
        seen.add(phone)
        out.append(
            Candidate(
                phone_e164=phone,
                conversation_id=row.conversation_id,
                locale=None,
            )
        )
        if len(out) >= limit:
            break
    return out
