"""THE CHOKE POINT. Every WhatsApp send crosses ``resolve_route()``.

QCP drives two Meta numbers and the separation between them is the whole
point of the platform:

* **Quata Verify** — ``purpose='authentication'``. OTP, login codes, PIN
  resets, device verification. Approved templates of the ``authentication``
  category and nothing else — never utility, never marketing, never
  free-form. Transaction and security alerts live on QUATA as utility, which
  is where Meta expects them.
* **QUATA** — ``purpose='engagement'``. Support, AI, campaigns, order and
  delivery updates, promotions.

Meta restricts numbers that send marketing on an authentication template. So
the separation is enforced in four independent layers, each sufficient on its
own:

* **L1 — the database.** ``whatsapp_messages`` carries a denormalised
  ``account_purpose`` with composite FKs to both ``whatsapp_accounts(id,
  purpose)`` and ``whatsapp_templates(id, account_purpose)``, and
  ``whatsapp_templates`` has CHECKs pinning auth-only-on-Verify,
  marketing-never-on-Verify, and Verify-takes-nothing-but-authentication.
  A violating row cannot exist.
  *(Composite FKs are enforced by Postgres. SQLite does not enable ``PRAGMA
  foreign_keys`` in this repo, so in dev L1 is carried by the CHECK
  constraints alone and L2–L4 do the rest.)*
* **L2 — this module.** ``resolve_route()`` is the only producer of a
  ``SendTicket``, and a ``SendTicket`` is the only thing ``meta.py`` will
  send. Eight ordered checks; the first failure raises ``RoutingDenied`` with
  a stable reason code and writes a ``whatsapp_audit_log`` row.
* **L3 — ``meta.py``.** It re-verifies the ticket's HMAC and re-asserts the
  purpose rules from the ticket's own fields before issuing any HTTP.
* **L4 — a test.** ``tests/test_whatsapp_boundaries.py`` asserts that
  ``dispatch.py`` is the only module in the app that may import ``meta``.

This module imports models, settings and audit. It must **never** import
``meta`` or ``dispatch`` — that is asserted by the boundary test.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass
from typing import Optional, Sequence

from sqlalchemy.orm import Session

from app.core.config import settings as env_settings
from app.models import (
    WhatsAppAccount,
    WhatsAppMessage,
    WhatsAppProduct,
    WhatsAppRoutingRule,
    WhatsAppTemplate,
)

from . import audit, settings_store


PURPOSE_AUTHENTICATION = "authentication"
PURPOSE_ENGAGEMENT = "engagement"

CATEGORY_AUTHENTICATION = "authentication"
CATEGORY_MARKETING = "marketing"
CATEGORY_UTILITY = "utility"

KIND_TEMPLATE = "template"


# ---------------------------------------------------------------------------
# Denial
# ---------------------------------------------------------------------------

class RoutingDenied(Exception):
    """A send was refused. ``reason`` is a stable code, never free text.

    The optional context is what the resolver had established *before* it
    refused. ``dispatch`` uses it to write the fullest ``suppressed`` message
    row the schema's CHECK constraints will accept, and the audit row always
    records the denial whether or not a message row is possible.
    """

    def __init__(
        self,
        reason: str,
        *,
        product_id: Optional[int] = None,
        account_id: Optional[int] = None,
        account_purpose: Optional[str] = None,
        template_id: Optional[int] = None,
        intent: Optional[str] = None,
        kind: Optional[str] = None,
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.product_id = product_id
        self.account_id = account_id
        self.account_purpose = account_purpose
        self.template_id = template_id
        self.intent = intent
        self.kind = kind


# Every reason code this module can raise. Kept as a set so the admin console
# and the tests can enumerate them without scraping the source.
REASONS = frozenset(
    {
        "product_disabled",
        "no_route",
        "purpose_not_permitted",
        "no_account_for_purpose",
        "freeform_on_auth_account",
        "template_not_approved",
        "purpose_mismatch",
        "auth_template_off_verify",
        "marketing_on_auth_account",
        "non_auth_template_on_verify",
        "missing_template_category",
        "template_account_mismatch",
        "variable_arity_mismatch",
        "delivery_disabled",
        "invalid_ticket",
        "message_not_routable",
    }
)


# ---------------------------------------------------------------------------
# The ticket
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SendTicket:
    """Permission to send exactly one message, signed with ``SECRET_KEY``.

    Frozen, so a resolved ticket cannot be edited in flight. ``checksum``
    covers every other field, and ``meta.py`` recomputes it with
    ``hmac.compare_digest`` before touching the network — forging one
    requires ``SECRET_KEY``.
    """

    ticket_id: str
    account_id: int
    account_purpose: str
    phone_number_id: str
    template_id: Optional[int]
    template_name: Optional[str]
    template_language: Optional[str]
    template_category: Optional[str]
    product_id: int
    intent: str
    kind: str
    to_phone_e164: str
    variables: tuple[str, ...]
    checksum: str


def canonical(
    *,
    ticket_id: str,
    account_id: int,
    account_purpose: str,
    phone_number_id: str,
    template_id: Optional[int],
    template_name: Optional[str],
    template_language: Optional[str],
    template_category: Optional[str],
    product_id: int,
    intent: str,
    kind: str,
    to_phone_e164: str,
    variables: Sequence[str],
) -> str:
    """Stable serialisation of every signed field. Order is part of the contract."""
    return json.dumps(
        [
            ticket_id,
            account_id,
            account_purpose,
            phone_number_id,
            template_id,
            template_name,
            template_language,
            template_category,
            product_id,
            intent,
            kind,
            to_phone_e164,
            list(variables),
        ],
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _sign(payload: str) -> str:
    return hmac.new(
        env_settings.SECRET_KEY.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def ticket_checksum(ticket: SendTicket) -> str:
    """Recompute the checksum a ticket *should* carry."""
    return _sign(
        canonical(
            ticket_id=ticket.ticket_id,
            account_id=ticket.account_id,
            account_purpose=ticket.account_purpose,
            phone_number_id=ticket.phone_number_id,
            template_id=ticket.template_id,
            template_name=ticket.template_name,
            template_language=ticket.template_language,
            template_category=ticket.template_category,
            product_id=ticket.product_id,
            intent=ticket.intent,
            kind=ticket.kind,
            to_phone_e164=ticket.to_phone_e164,
            variables=ticket.variables,
        )
    )


def verify_ticket(ticket: SendTicket) -> None:
    """Raise ``RoutingDenied`` unless the ticket is authentic *and* legal.

    Called by ``meta.py`` as its first statement (L3). Two independent
    failures are caught here:

    1. a tampered or hand-constructed ticket — the HMAC will not match;
    2. a ticket that is authentic but describes an illegal pairing — which is
       what a bug in L2, or a future caller minting its own ticket with the
       real key, would produce.
    """
    if not isinstance(ticket, SendTicket):
        raise RoutingDenied("invalid_ticket")
    if not hmac.compare_digest(ticket.checksum, ticket_checksum(ticket)):
        raise RoutingDenied("invalid_ticket")
    # The ticket carries one purpose and one category, so every category rule
    # is re-checkable here: nothing but an authentication template leaves
    # Verify, no authentication template leaves QUATA, and a template send
    # that states no category at all is refused rather than skipped. The
    # template↔account *binding* is not on the ticket and cannot be re-checked
    # from its fields — that is carried by L1 and by ``rebuild_ticket``, which
    # is why ``template_account_purpose`` is passed as None here.
    assert_purpose_compatible(
        account_purpose=ticket.account_purpose,
        template_account_purpose=None,
        template_category=ticket.template_category,
        kind=ticket.kind,
    )


# ---------------------------------------------------------------------------
# The purpose assertions — used by resolve_route (L2) and meta.py (L3)
# ---------------------------------------------------------------------------

def assert_purpose_compatible(
    *,
    account_purpose: str,
    template_account_purpose: Optional[str],
    template_category: Optional[str],
    kind: str,
) -> None:
    """The rules, all explicit, none inferred.

    Split out of ``resolve_route`` so the transport can re-run exactly the
    same logic on the ticket's own fields, and so the impossible pairings
    (which the database refuses to store) are still directly testable.
    """
    if account_purpose == PURPOSE_AUTHENTICATION and kind != KIND_TEMPLATE:
        # The Verify number can only ever emit approved templates.
        raise RoutingDenied("freeform_on_auth_account")
    if template_category is None:
        # A template send that states no category cannot be checked against
        # any of the rules below, so it is refused rather than waved through:
        # at L3 the ticket's own fields are all there is, and an absent
        # category used to skip every remaining rule.
        if kind == KIND_TEMPLATE:
            raise RoutingDenied("missing_template_category")
        return
    if template_account_purpose is not None and template_account_purpose != account_purpose:
        raise RoutingDenied("purpose_mismatch")
    if template_category == CATEGORY_AUTHENTICATION and account_purpose != PURPOSE_AUTHENTICATION:
        raise RoutingDenied("auth_template_off_verify")
    if template_category == CATEGORY_MARKETING and account_purpose == PURPOSE_AUTHENTICATION:
        raise RoutingDenied("marketing_on_auth_account")
    # The Verify number takes the authentication category and nothing else.
    # ``utility`` used to match neither of the two rules above and was
    # therefore accepted on Verify by omission. ``category`` was also
    # operator-typed data that nothing re-synced from Meta, so a template Meta
    # had since re-classified as MARKETING kept leaving the verification
    # number; ``templates.sync_from_meta`` now re-syncs it and quarantines a
    # re-classified row, but this check stays because a row can be stale
    # between syncs. Transaction and security alerts belong on QUATA as
    # utility.
    if account_purpose == PURPOSE_AUTHENTICATION and template_category != CATEGORY_AUTHENTICATION:
        raise RoutingDenied("non_auth_template_on_verify")


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

def _deny(
    db: Session,
    reason: str,
    *,
    product_slug: str,
    intent: str,
    kind: str,
    product_id: Optional[int] = None,
    account_id: Optional[int] = None,
    account_purpose: Optional[str] = None,
    template_id: Optional[int] = None,
) -> RoutingDenied:
    """Record the denial, then hand back the exception for the caller to raise."""
    audit.record(
        db,
        action="routing.denied",
        resource_type="whatsapp_route",
        resource_id=f"{product_slug}:{intent}",
        outcome=audit.OUTCOME_DENIED,
        reason=reason,
        product_id=product_id,
        account_id=account_id,
        details={"product": product_slug, "intent": intent, "kind": kind},
    )
    return RoutingDenied(
        reason,
        product_id=product_id,
        account_id=account_id,
        account_purpose=account_purpose,
        template_id=template_id,
        intent=intent,
        kind=kind,
    )


def _find_rule(
    db: Session, *, product_id: int, intent: str, locale: Optional[str]
) -> Optional[WhatsAppRoutingRule]:
    """Active rule for this intent. An exact locale match beats the NULL (any) rule."""
    rows = (
        db.query(WhatsAppRoutingRule)
        .filter(WhatsAppRoutingRule.product_id == product_id)
        .filter(WhatsAppRoutingRule.intent == intent)
        .filter(WhatsAppRoutingRule.is_active == True)  # noqa: E712
        .order_by(WhatsAppRoutingRule.priority, WhatsAppRoutingRule.id)
        .all()
    )
    if not rows:
        return None
    if locale:
        for row in rows:
            if row.locale == locale:
                return row
    for row in rows:
        if row.locale in (None, ""):
            return row
    return None


def _find_template(
    db: Session, *, account_id: int, intent: str, language: str
) -> Optional[WhatsAppTemplate]:
    return (
        db.query(WhatsAppTemplate)
        .filter(WhatsAppTemplate.account_id == account_id)
        .filter(WhatsAppTemplate.intent == intent)
        .filter(WhatsAppTemplate.language == language)
        .filter(WhatsAppTemplate.status == "approved")
        .order_by(WhatsAppTemplate.id)
        .first()
    )


def resolve_route(
    db: Session,
    *,
    product_slug: str,
    intent: str,
    to_phone_e164: str,
    kind: str = KIND_TEMPLATE,
    locale: Optional[str] = None,
    variables: tuple[str, ...] = (),
) -> SendTicket:
    """Resolve one send request into a signed ``SendTicket``, or refuse it.

    Eight ordered checks. The first failure raises ``RoutingDenied`` and
    leaves a ``whatsapp_audit_log`` row with ``outcome='denied'`` behind it.
    Only after all eight is a ticket minted and stamped.

    ``variables`` are the *clear* template values (an OTP included). They are
    signed into the ticket and handed to the transport; they are never logged
    and never persisted in clear — see ``redaction.redact_variables``.
    """
    product = (
        db.query(WhatsAppProduct).filter(WhatsAppProduct.slug == product_slug).first()
    )

    # 1 ─ the per-product migration gate.
    if product is None or not product.is_enabled:
        raise _deny(
            db,
            "product_disabled",
            product_slug=product_slug,
            intent=intent,
            kind=kind,
            product_id=product.id if product else None,
        )

    # 2 ─ a route must exist, be active, and be unconditional (v1).
    rule = _find_rule(db, product_id=product.id, intent=intent, locale=locale)
    if rule is None or (rule.conditions or {}):
        raise _deny(
            db,
            "no_route",
            product_slug=product_slug,
            intent=intent,
            kind=kind,
            product_id=product.id,
        )

    # 3 ─ the product must be entitled to this account purpose at all.
    allowed = product.allowed_purposes or []
    if rule.purpose not in allowed:
        raise _deny(
            db,
            "purpose_not_permitted",
            product_slug=product_slug,
            intent=intent,
            kind=kind,
            product_id=product.id,
        )

    # 4 ─ a live number must exist for that purpose.
    account = (
        db.query(WhatsAppAccount)
        .filter(WhatsAppAccount.purpose == rule.purpose)
        .filter(WhatsAppAccount.is_active == True)  # noqa: E712
        .order_by(WhatsAppAccount.id)
        .first()
    )
    if account is None:
        raise _deny(
            db,
            "no_account_for_purpose",
            product_slug=product_slug,
            intent=intent,
            kind=kind,
            product_id=product.id,
        )

    # 5 ─ the Verify number can only ever emit approved templates.
    if account.purpose == PURPOSE_AUTHENTICATION and kind != KIND_TEMPLATE:
        raise _deny(
            db,
            "freeform_on_auth_account",
            product_slug=product_slug,
            intent=intent,
            kind=kind,
            product_id=product.id,
            account_id=account.id,
            account_purpose=account.purpose,
        )

    language = (locale or product.default_locale or "en").strip() or "en"
    template: Optional[WhatsAppTemplate] = None

    if kind == KIND_TEMPLATE:
        # 6 ─ an approved template must exist on *that* account.
        template = _find_template(
            db, account_id=account.id, intent=rule.template_intent, language=language
        )
        if template is None:
            raise _deny(
                db,
                "template_not_approved",
                product_slug=product_slug,
                intent=intent,
                kind=kind,
                product_id=product.id,
                account_id=account.id,
                account_purpose=account.purpose,
            )

        # 7 ─ the purpose assertions, plus arity.
        try:
            assert_purpose_compatible(
                account_purpose=account.purpose,
                template_account_purpose=template.account_purpose,
                template_category=template.category,
                kind=kind,
            )
        except RoutingDenied as exc:
            raise _deny(
                db,
                exc.reason,
                product_slug=product_slug,
                intent=intent,
                kind=kind,
                product_id=product.id,
                account_id=account.id,
                account_purpose=account.purpose,
                template_id=template.id,
            ) from exc

        if len(variables) != len(template.variables or []):
            raise _deny(
                db,
                "variable_arity_mismatch",
                product_slug=product_slug,
                intent=intent,
                kind=kind,
                product_id=product.id,
                account_id=account.id,
                account_purpose=account.purpose,
                template_id=template.id,
            )

    # 8 ─ dormancy. Checked last so a suppressed row still carries the full
    # resolution — "what would have been sent" is answerable.
    if not settings_store.delivery_enabled():
        raise _deny(
            db,
            "delivery_disabled",
            product_slug=product_slug,
            intent=intent,
            kind=kind,
            product_id=product.id,
            account_id=account.id,
            account_purpose=account.purpose,
            template_id=template.id if template else None,
        )

    return _mint(
        account=account,
        product_id=product.id,
        template=template,
        intent=intent,
        kind=kind,
        to_phone_e164=to_phone_e164,
        variables=tuple(str(v) for v in variables),
    )


def _mint(
    *,
    account: WhatsAppAccount,
    product_id: int,
    template: Optional[WhatsAppTemplate],
    intent: str,
    kind: str,
    to_phone_e164: str,
    variables: tuple[str, ...],
) -> SendTicket:
    ticket_id = uuid.uuid4().hex
    fields = dict(
        ticket_id=ticket_id,
        account_id=account.id,
        account_purpose=account.purpose,
        phone_number_id=account.phone_number_id,
        template_id=template.id if template else None,
        template_name=template.name if template else None,
        template_language=template.language if template else None,
        template_category=template.category if template else None,
        product_id=product_id,
        intent=intent,
        kind=kind,
        to_phone_e164=to_phone_e164,
        variables=variables,
    )
    return SendTicket(**fields, checksum=_sign(canonical(**fields)))


def rebuild_ticket(
    db: Session, message: WhatsAppMessage, *, variables: tuple[str, ...]
) -> SendTicket:
    """Mint a ticket for a queued row on its way to the transport.

    A retry (or the RQ worker picking up a hand-off) has a row, not a ticket.
    Rather than trust the row, this re-reads the account and template and
    re-runs the same assertions, so the invariant is crossed a *second* time
    on the way out. Anything inconsistent raises ``RoutingDenied`` and the
    message is failed rather than sent.
    """
    account = (
        db.query(WhatsAppAccount).filter(WhatsAppAccount.id == message.account_id).first()
    )
    if account is None or not account.is_active:
        raise RoutingDenied("no_account_for_purpose", account_id=message.account_id)
    if account.purpose != message.account_purpose:
        # Only reachable if a row was written around the composite FK.
        raise RoutingDenied("purpose_mismatch", account_id=account.id)

    product = (
        db.query(WhatsAppProduct).filter(WhatsAppProduct.id == message.product_id).first()
        if message.product_id
        else None
    )
    if product is None or not product.is_enabled:
        raise RoutingDenied("product_disabled", account_id=account.id, product_id=message.product_id)

    template: Optional[WhatsAppTemplate] = None
    if message.template_id is not None:
        template = (
            db.query(WhatsAppTemplate)
            .filter(WhatsAppTemplate.id == message.template_id)
            .first()
        )
        if template is None or template.status != "approved":
            raise RoutingDenied("template_not_approved", account_id=account.id)
        if template.account_id != account.id:
            # Purposes can match while the accounts do not — a number
            # migration leaves the retired WABA's templates in the table.
            # Meta rejects a template it does not know on this number, and
            # the rejection costs an attempt.
            raise RoutingDenied(
                "template_account_mismatch",
                account_id=account.id,
                template_id=template.id,
            )

    # Ordered before the assertions so a template row with no template still
    # denies with the reason that names its actual defect, rather than with
    # "no category" — which is only the symptom of the missing template.
    if message.kind == KIND_TEMPLATE and template is None:
        raise RoutingDenied("message_not_routable", account_id=account.id)
    assert_purpose_compatible(
        account_purpose=account.purpose,
        template_account_purpose=template.account_purpose if template else None,
        template_category=template.category if template else None,
        kind=message.kind,
    )
    if template is not None and len(variables) != len(template.variables or []):
        raise RoutingDenied("variable_arity_mismatch", account_id=account.id)
    if not settings_store.delivery_enabled():
        raise RoutingDenied("delivery_disabled", account_id=account.id)

    return _mint(
        account=account,
        product_id=product.id,
        template=template,
        intent=message.intent or "",
        kind=message.kind,
        to_phone_e164=message.to_phone_e164 or "",
        variables=tuple(str(v) for v in variables),
    )
