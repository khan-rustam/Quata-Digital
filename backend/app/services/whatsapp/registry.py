"""Routing rules — the table ``routing.resolve_route`` reads, and its guards.

A routing rule answers one question: *product + intent + locale → which
number, and which template on it*. Until this module existed there was no way
to write one except by hand in SQL, which is how the estate ended up with
categories nobody had checked sitting on the verification number.

Every guard here exists because the mistake it catches is silent:

* **an intent with no rule** — the product's send is refused with ``no_route``
  and the product usually treats that as "WhatsApp is off today";
* **two rules colliding** — ``uq_whatsapp_routing_product_intent_locale``
  refuses the second one, but only after the operator has typed it;
* **a rule pointing at a retired or unapproved template** — resolution walks
  all the way to ``template_not_approved`` at send time, i.e. when a customer
  is waiting for an OTP;
* **a rule that routes authentication traffic to the engagement number** —
  the one that gets a number restricted.

Severity is what makes the guards usable rather than obstructive:

``error``       refuses the write outright.
``activation``  a rule may be *created* with this problem — an operator
                legitimately builds the rule before the template is approved —
                but it may not be switched on.
``warning``     reported and nothing else. "No live number for this purpose"
                is a warning, not an error: QCP ships dormant, and rules have
                to be preparable before the number is switched on.

**A new rule is always created inactive.** Turning one on is a separate,
audited act, and nothing in this module can enable a product, activate an
account or turn delivery on.
"""
from __future__ import annotations

import hashlib
import json
from typing import Optional

from sqlalchemy.orm import Session

from app.models import (
    WhatsAppAccount,
    WhatsAppProduct,
    WhatsAppRoutingRule,
    WhatsAppTemplate,
)

from . import audit, settings_store


SEVERITY_ERROR = "error"
SEVERITY_ACTIVATION = "activation"
SEVERITY_WARNING = "warning"

PURPOSES = ("authentication", "engagement")
FALLBACK_CHANNELS = ("email", "sms", "none")

# ``activation`` blocks switching a rule on; ``error`` blocks everything.
_BLOCKS_ACTIVATION = (SEVERITY_ERROR, SEVERITY_ACTIVATION)


class RuleRefused(Exception):
    """A routing write was refused, with the code and the sentence."""

    def __init__(self, reason: str, detail: str, *, problems: Optional[list] = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.detail = detail
        self.problems = problems or []


def _fingerprint(value) -> str:
    blob = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


def _snapshot(rule: WhatsAppRoutingRule) -> dict:
    return {
        "product_id": rule.product_id,
        "intent": rule.intent,
        "purpose": rule.purpose,
        "template_intent": rule.template_intent,
        "locale": rule.locale,
        "priority": rule.priority,
        "is_active": rule.is_active,
        "fallback_channel": rule.fallback_channel,
        "conditions": rule.conditions or {},
    }


def blocked_state(
    rule: WhatsAppRoutingRule, product: Optional[WhatsAppProduct]
) -> tuple[Optional[str], Optional[str]]:
    """Why this rule carries nothing despite being switched on — or (None, None).

    ``check_rule`` already refuses to *create* or *activate* a rule for a
    purpose the product may not reach. What nothing covered is the world
    moving underneath a rule that is already live: revoking a product's
    authentication grant leaves its old ``purpose='authentication'`` rules
    with ``is_active=True``. ``routing.resolve_route`` re-checks the grant, so
    the send is genuinely refused and no traffic is at risk — but the console
    reads ``is_active`` and told the operator the OTP path was up. Believing
    an OTP path exists that does not is exactly how QuataFood's no-fallback
    login ends up unmonitored.

    Cheap on purpose: no queries, just the two fields, so the list endpoint
    can call it per row.
    """
    if product is None:
        return (None, None)
    allowed = [str(p) for p in (product.allowed_purposes or [])]
    if rule.purpose not in allowed:
        return (
            "purpose_not_permitted",
            f"{product.slug} is no longer entitled to the '{rule.purpose}' "
            "number, so this rule carries no traffic even though it is "
            "switched on. Deactivate it, or restore the grant deliberately "
            f"via POST /admin/qcp/products/{product.slug}/purposes/authentication.",
        )
    return (None, None)


def rule_out(
    rule: WhatsAppRoutingRule,
    *,
    product_slug: Optional[str] = None,
    product: Optional[WhatsAppProduct] = None,
) -> dict:
    """Public shape. Carries no credential of any kind — there is none here.

    ``is_active`` stays the stored truth; ``is_blocked`` and
    ``is_effectively_live`` are what the screen should render, so that a rule
    the world has invalidated cannot be displayed as live. Judging that needs
    the product, and without one the honest answer is "not known to be
    blocked" rather than a guess.
    """
    reason, detail = blocked_state(rule, product)
    return {
        "id": rule.id,
        "product_id": rule.product_id,
        "product": product_slug or (product.slug if product else None),
        "intent": rule.intent,
        "purpose": rule.purpose,
        "template_intent": rule.template_intent,
        "locale": rule.locale,
        "priority": rule.priority,
        "is_active": rule.is_active,
        "is_blocked": reason is not None,
        "blocked_reason": reason,
        "blocked_detail": detail,
        "is_effectively_live": bool(rule.is_active) and reason is None,
        "fallback_channel": rule.fallback_channel,
        "conditions": rule.conditions or {},
        "created_at": rule.created_at,
        "updated_at": rule.updated_at,
    }


# ---------------------------------------------------------------------------
# The guards
# ---------------------------------------------------------------------------

def _problem(code: str, severity: str, detail: str) -> dict:
    return {"code": code, "severity": severity, "detail": detail}


def check_rule(
    db: Session,
    *,
    product: WhatsAppProduct,
    intent: str,
    purpose: str,
    template_intent: str,
    locale: Optional[str],
    exclude_id: Optional[int] = None,
) -> list[dict]:
    """Everything wrong with this rule, most serious first.

    Ordered so that the first ``error`` is the one worth showing: a product
    that may not reach a purpose at all is a more useful message than the
    template problem that follows from it.
    """
    problems: list[dict] = []

    if purpose not in PURPOSES:
        problems.append(
            _problem(
                "invalid_purpose",
                SEVERITY_ERROR,
                f"'{purpose}' is not a QCP account purpose ({', '.join(PURPOSES)}).",
            )
        )
        return problems

    if purpose not in (product.allowed_purposes or []):
        problems.append(
            _problem(
                "purpose_not_permitted",
                SEVERITY_ERROR,
                f"{product.slug} is not entitled to the '{purpose}' number. "
                "Widen allowed_purposes first — deliberately, and on its own.",
            )
        )

    clash = (
        db.query(WhatsAppRoutingRule)
        .filter(WhatsAppRoutingRule.product_id == product.id)
        .filter(WhatsAppRoutingRule.intent == intent)
        .filter(
            WhatsAppRoutingRule.locale.is_(None)
            if locale in (None, "")
            else WhatsAppRoutingRule.locale == locale
        )
    )
    if exclude_id is not None:
        clash = clash.filter(WhatsAppRoutingRule.id != exclude_id)
    existing = clash.first()
    if existing is not None:
        problems.append(
            _problem(
                "duplicate_rule",
                SEVERITY_ERROR,
                f"Rule #{existing.id} already routes {product.slug}/{intent} for "
                f"locale {locale or 'any'}. Edit it rather than adding a second.",
            )
        )

    # Scoped to the numbers that are actually live, exactly as
    # ``routing._find_template`` scopes its lookup. A number migration leaves
    # the retired WABA's templates in the table, and judging a rule against
    # those would call it routable when the send would fail at Meta. With no
    # live number at all (QCP's dormant default) there is nothing to scope to,
    # so the whole table is the best available evidence.
    live_ids = [
        row.id
        for row in db.query(WhatsAppAccount)
        .filter(WhatsAppAccount.is_active == True)  # noqa: E712
        .all()
    ]
    candidate_query = db.query(WhatsAppTemplate).filter(
        WhatsAppTemplate.intent == template_intent
    )
    if live_ids:
        candidate_query = candidate_query.filter(WhatsAppTemplate.account_id.in_(live_ids))
    candidates = candidate_query.all()
    if not candidates:
        problems.append(
            _problem(
                "no_template_for_intent",
                SEVERITY_ACTIVATION,
                f"No template declares the intent '{template_intent}'. The rule "
                "can be prepared, but it cannot carry traffic.",
            )
        )
    else:
        auth = [t for t in candidates if t.category == "authentication"]
        if auth and purpose != "authentication":
            problems.append(
                _problem(
                    "auth_traffic_on_engagement_number",
                    SEVERITY_ERROR,
                    f"'{template_intent}' is an authentication template and lives "
                    "on Quata Verify. Routing it through the engagement number is "
                    "the exact pairing the two-number split exists to prevent.",
                )
            )
        if not auth and purpose == "authentication":
            problems.append(
                _problem(
                    "non_auth_template_on_verify",
                    SEVERITY_ERROR,
                    f"'{template_intent}' is not an authentication template, and "
                    "the Quata Verify number carries nothing else. Transaction "
                    "and security alerts belong on QUATA as utility.",
                )
            )

    approved = [
        t
        for t in candidates
        if t.status == "approved" and t.account_purpose == purpose
    ]
    if candidates and not approved:
        problems.append(
            _problem(
                "template_not_approved",
                SEVERITY_ACTIVATION,
                f"No approved '{template_intent}' template exists on the "
                f"'{purpose}' number. A locally created template stays "
                "unapproved until a sync confirms Meta approved it; a retired "
                "one never sends again.",
            )
        )

    live = (
        db.query(WhatsAppAccount)
        .filter(WhatsAppAccount.purpose == purpose)
        .filter(WhatsAppAccount.is_active == True)  # noqa: E712
        .first()
    )
    if live is None:
        problems.append(
            _problem(
                "no_account_for_purpose",
                SEVERITY_WARNING,
                f"No live '{purpose}' number yet. QCP is dormant by design, so "
                "this is expected — the rule is prepared, not broken.",
            )
        )
    if not product.is_enabled:
        problems.append(
            _problem(
                "product_disabled",
                SEVERITY_WARNING,
                f"{product.slug} is not switched on yet, so no traffic reaches "
                "this rule regardless of its state.",
            )
        )

    order = {SEVERITY_ERROR: 0, SEVERITY_ACTIVATION: 1, SEVERITY_WARNING: 2}
    problems.sort(key=lambda p: order[p["severity"]])
    return problems


def _first(problems: list[dict], severities: tuple[str, ...]) -> Optional[dict]:
    return next((p for p in problems if p["severity"] in severities), None)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def create_rule(
    db: Session,
    *,
    product: WhatsAppProduct,
    intent: str,
    purpose: str,
    template_intent: str,
    locale: Optional[str] = None,
    priority: int = 100,
    fallback_channel: Optional[str] = None,
    actor_id: Optional[int] = None,
    ip_address: Optional[str] = None,
) -> tuple[WhatsAppRoutingRule, list[dict]]:
    """Create one rule, **inactive**. Returns it with its outstanding problems."""
    intent = str(intent or "").strip()[:80]
    template_intent = str(template_intent or "").strip()[:80]
    locale = (locale or None) or None
    problems = check_rule(
        db,
        product=product,
        intent=intent,
        purpose=purpose,
        template_intent=template_intent,
        locale=locale,
    )
    blocking = _first(problems, (SEVERITY_ERROR,))
    if blocking is not None:
        audit.record(
            db,
            action="routing_rule.create_denied",
            resource_type="whatsapp_routing_rule",
            resource_id=f"{product.slug}:{intent}",
            outcome=audit.OUTCOME_DENIED,
            reason=blocking["code"],
            actor_id=actor_id,
            product_id=product.id,
            details={"intent": intent, "purpose": purpose, "template_intent": template_intent},
            ip_address=ip_address,
        )
        db.commit()
        raise RuleRefused(blocking["code"], blocking["detail"], problems=problems)

    if fallback_channel is not None and fallback_channel not in FALLBACK_CHANNELS:
        raise RuleRefused(
            "invalid_fallback_channel",
            f"'{fallback_channel}' is not one of {', '.join(FALLBACK_CHANNELS)}.",
        )

    rule = WhatsAppRoutingRule(
        product_id=product.id,
        intent=intent,
        purpose=purpose,
        template_intent=template_intent,
        locale=locale,
        priority=int(priority),
        # Always. A rule that arrived active would be a routing change nobody
        # decided to make.
        is_active=False,
        fallback_channel=fallback_channel,
        conditions={},
    )
    db.add(rule)
    db.flush()
    audit.record(
        db,
        action="routing_rule.created",
        resource_type="whatsapp_routing_rule",
        resource_id=str(rule.id),
        outcome=audit.OUTCOME_OK,
        actor_id=actor_id,
        product_id=product.id,
        details={
            "before_fingerprint": _fingerprint(None),
            "after_fingerprint": _fingerprint(_snapshot(rule)),
            "created": _snapshot(rule),
            "problems": [p["code"] for p in problems],
        },
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(rule)
    return rule, problems


EDITABLE = ("purpose", "template_intent", "locale", "priority", "fallback_channel")


def update_rule(
    db: Session,
    rule: WhatsAppRoutingRule,
    *,
    changes: dict,
    product: WhatsAppProduct,
    actor_id: Optional[int] = None,
    ip_address: Optional[str] = None,
) -> tuple[WhatsAppRoutingRule, list[dict]]:
    """Edit a rule. ``is_active`` is not editable here — see ``set_active``."""
    unknown = set(changes) - set(EDITABLE)
    if unknown:
        raise RuleRefused(
            "field_not_editable", f"Not editable here: {', '.join(sorted(unknown))}."
        )
    before = _snapshot(rule)
    merged = {**before, **{k: v for k, v in changes.items() if v is not None or k == "locale"}}

    problems = check_rule(
        db,
        product=product,
        intent=rule.intent,
        purpose=merged["purpose"],
        template_intent=merged["template_intent"],
        locale=merged["locale"],
        exclude_id=rule.id,
    )
    blocking = _first(problems, (SEVERITY_ERROR,))
    if blocking is not None:
        raise RuleRefused(blocking["code"], blocking["detail"], problems=problems)
    # An edit that invalidates a live rule takes it out of service rather than
    # leaving it pointed somewhere it cannot go.
    if rule.is_active and _first(problems, _BLOCKS_ACTIVATION) is not None:
        raise RuleRefused(
            _first(problems, _BLOCKS_ACTIVATION)["code"],
            "This rule is live. Deactivate it before editing it into a state "
            "it could not be switched on from.",
            problems=problems,
        )

    for field in EDITABLE:
        if field in changes and (changes[field] is not None or field == "locale"):
            setattr(rule, field, changes[field])
    db.flush()
    after = _snapshot(rule)
    audit.record(
        db,
        action="routing_rule.updated",
        resource_type="whatsapp_routing_rule",
        resource_id=str(rule.id),
        outcome=audit.OUTCOME_OK,
        actor_id=actor_id,
        product_id=rule.product_id,
        details={
            "before_fingerprint": _fingerprint(before),
            "after_fingerprint": _fingerprint(after),
            "changed": {
                f: {"from": before[f], "to": after[f]}
                for f in after
                if before[f] != after[f]
            },
        },
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(rule)
    return rule, problems


def set_active(
    db: Session,
    rule: WhatsAppRoutingRule,
    *,
    active: bool,
    product: WhatsAppProduct,
    actor_id: Optional[int] = None,
    ip_address: Optional[str] = None,
) -> tuple[WhatsAppRoutingRule, list[dict]]:
    """Switch a rule on or off.

    Switching **off** is never refused — stopping traffic must always be
    possible. Switching **on** re-runs every guard, because the world has
    moved since the rule was written: the template it names may since have
    been retired, or re-classified by a sync.
    """
    problems = check_rule(
        db,
        product=product,
        intent=rule.intent,
        purpose=rule.purpose,
        template_intent=rule.template_intent,
        locale=rule.locale,
        exclude_id=rule.id,
    )
    if active:
        blocking = _first(problems, _BLOCKS_ACTIVATION)
        if blocking is not None:
            audit.record(
                db,
                action="routing_rule.activate_denied",
                resource_type="whatsapp_routing_rule",
                resource_id=str(rule.id),
                outcome=audit.OUTCOME_DENIED,
                reason=blocking["code"],
                actor_id=actor_id,
                product_id=rule.product_id,
                details={"intent": rule.intent, "template_intent": rule.template_intent},
                ip_address=ip_address,
            )
            db.commit()
            raise RuleRefused(blocking["code"], blocking["detail"], problems=problems)

    before = _snapshot(rule)
    rule.is_active = bool(active)
    db.flush()
    audit.record(
        db,
        action="routing_rule.activated" if active else "routing_rule.deactivated",
        resource_type="whatsapp_routing_rule",
        resource_id=str(rule.id),
        outcome=audit.OUTCOME_OK,
        actor_id=actor_id,
        product_id=rule.product_id,
        details={
            "before_fingerprint": _fingerprint(before),
            "after_fingerprint": _fingerprint(_snapshot(rule)),
            "changed": {"is_active": {"from": before["is_active"], "to": bool(active)}},
        },
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(rule)
    return rule, problems


def delete_rule(
    db: Session,
    rule: WhatsAppRoutingRule,
    *,
    actor_id: Optional[int] = None,
    ip_address: Optional[str] = None,
) -> dict:
    """Remove a rule. The audit row keeps what it was."""
    before = _snapshot(rule)
    rule_id = rule.id
    product_id = rule.product_id
    db.delete(rule)
    db.flush()
    audit.record(
        db,
        action="routing_rule.deleted",
        resource_type="whatsapp_routing_rule",
        resource_id=str(rule_id),
        outcome=audit.OUTCOME_OK,
        actor_id=actor_id,
        product_id=product_id,
        details={
            "before_fingerprint": _fingerprint(before),
            "after_fingerprint": _fingerprint(None),
            "deleted": before,
        },
        ip_address=ip_address,
    )
    db.commit()
    return before


# ---------------------------------------------------------------------------
# Coverage — the questions nobody thinks to ask until an OTP goes missing
# ---------------------------------------------------------------------------

def coverage(db: Session, product: WhatsAppProduct) -> dict:
    """Where this product's routing has holes."""
    rules = (
        db.query(WhatsAppRoutingRule)
        .filter(WhatsAppRoutingRule.product_id == product.id)
        .all()
    )
    templates = (
        db.query(WhatsAppTemplate)
        .filter(WhatsAppTemplate.product_id == product.id)
        .all()
    )

    routed = {r.template_intent for r in rules}
    template_intents = {t.intent for t in templates}
    approved_intents = {t.intent for t in templates if t.status == "approved"}

    by_intent: dict[str, list[WhatsAppRoutingRule]] = {}
    for rule in rules:
        by_intent.setdefault(rule.intent, []).append(rule)

    return {
        "product": product.slug,
        # A template exists for it and nothing routes to it: the product asks
        # and gets ``no_route``.
        "template_intents_without_rule": sorted(template_intents - routed),
        # A rule names a template intent that no template declares.
        "rules_without_template": sorted(
            {r.template_intent for r in rules if r.template_intent not in template_intents}
        ),
        # Rules exist for the intent but none of them is switched on.
        "intents_without_active_rule": sorted(
            intent for intent, group in by_intent.items() if not any(r.is_active for r in group)
        ),
        # Live rules pointed at something that cannot send today.
        "active_rules_without_approved_template": sorted(
            {
                r.template_intent
                for r in rules
                if r.is_active and r.template_intent not in approved_intents
            }
        ),
        # The audited QuataFood finding, made visible: an authentication route
        # with nothing to fall back on when WhatsApp is unavailable.
        "auth_rules_without_fallback": sorted(
            r.intent
            for r in rules
            if r.purpose == "authentication" and (r.fallback_channel or "none") == "none"
        ),
        "rules": len(rules),
        "active_rules": sum(1 for r in rules if r.is_active),
    }


# ---------------------------------------------------------------------------
# "Why does nothing send?" — the gates, named
# ---------------------------------------------------------------------------
#
# Four independent gates stand between a registered product and a delivered
# message, and they clear on wildly different timescales: minting a key is a
# click, switching a product on is a click, switching the platform on is a
# click and an env var — and a Meta template approval takes **days**, with
# nothing an operator can do to shorten it.
#
# Reporting only ``ok: false`` therefore produces a specific, repeatable
# failure: the operator re-checks the switches they can see, finds them all
# on, and concludes QCP is broken. This is the same argument
# ``settings_store.ai_reply_readiness`` makes about the AI switch — "a switch
# that is on and does nothing is the worst state an operator can be left in" —
# applied to the product onboarding path the owner's 2026-08-17 order runs
# through, one product at a time.
#
# The codes are ``routing.REASONS``, not a second vocabulary. A product told
# ``template_not_approved`` here is told ``template_not_approved`` by the send
# it tries next, and an operator grepping the audit log for a denial finds the
# word the console showed them. Deliberately *not* imported from ``routing``:
# ``routing`` imports nothing from here and the dependency must stay that way,
# so ``test_qcp_onboarding`` pins the two lists against each other instead.

GATE_NO_API_KEY = "no_api_key"
GATE_PRODUCT_DISABLED = "product_disabled"
GATE_NO_ROUTE = "no_route"
GATE_NO_ACCOUNT = "no_account_for_purpose"
GATE_TEMPLATE_NOT_APPROVED = "template_not_approved"
GATE_DELIVERY_DISABLED = "delivery_disabled"


def _gate(code: str, message: str) -> dict:
    return {"code": code, "message": message}


def product_gates(
    db: Session, product: WhatsAppProduct, *, include_key_gate: bool = False
) -> list[dict]:
    """Every gate this product is currently behind, in the order to clear them.

    Returns **all** of them, not the first. An operator planning a migration
    needs to know the template gate is shut *before* they spend an afternoon
    on the three that clear in a click, because that one is measured in days
    at Meta.

    ``include_key_gate`` is the one asymmetry between the two surfaces that
    call this. The product's own ``GET /whatsapp/health`` cannot report
    ``no_api_key``: reaching it at all requires a key, and answering an
    unauthenticated caller "that product exists but holds no key" would turn
    health into a probe for which products are worth attacking. So the
    operator's registry passes ``True`` and the gateway does not — and the
    gate is still reported, rather than being the one nothing names.

    Cheap enough for a list endpoint: three queries, none of them per rule.
    """
    gates: list[dict] = []
    allowed = [str(p) for p in (product.allowed_purposes or [])]

    if include_key_gate and not product.api_key_hash:
        gates.append(
            _gate(
                GATE_NO_API_KEY,
                "No API key has been minted, so this product cannot "
                "authenticate at the gateway. Mint one — it is shown once and "
                "cannot be recovered afterwards.",
            )
        )

    if not product.is_enabled:
        gates.append(
            _gate(
                GATE_PRODUCT_DISABLED,
                "This product has not been migrated onto QCP. Every send it "
                "makes is recorded as suppressed rather than delivered.",
            )
        )

    # ``blocked_state`` drops a rule the world has invalidated underneath —
    # an authentication rule left switched on after the grant was revoked
    # carries no traffic, and counting it here would report a route that
    # ``routing.resolve_route`` refuses.
    live_rules = [
        r
        for r in db.query(WhatsAppRoutingRule)
        .filter(WhatsAppRoutingRule.product_id == product.id)
        .filter(WhatsAppRoutingRule.is_active == True)  # noqa: E712
        .all()
        if blocked_state(r, product)[0] is None
    ]
    if not live_rules:
        gates.append(
            _gate(
                GATE_NO_ROUTE,
                "No active routing rule resolves any intent for this product, "
                "so every send is refused before a number is even chosen.",
            )
        )

    active_purposes = {
        purpose
        for (purpose,) in db.query(WhatsAppAccount.purpose)
        .filter(WhatsAppAccount.is_active == True)  # noqa: E712
        .all()
    }
    # What the live rules actually need; with no live rules, everything this
    # product is entitled to, so a product mid-setup still learns the number
    # it will need is dark.
    needed = {r.purpose for r in live_rules} or set(allowed)
    missing = sorted(p for p in needed if p not in active_purposes)
    if missing:
        gates.append(
            _gate(
                GATE_NO_ACCOUNT,
                "No WhatsApp number is switched on for the "
                + ", ".join(f"'{p}'" for p in missing)
                + " purpose, so nothing can carry this product's messages.",
            )
        )

    # The slow one. Only asked of rules that could otherwise send today —
    # a rule whose number is dark is already reported above, and naming it
    # twice reads as two problems.
    fallback_language = (product.default_locale or "en").strip() or "en"
    unapproved = sorted(
        {
            r.template_intent
            for r in live_rules
            if r.purpose in active_purposes
            and not _has_approved_template(
                db,
                purpose=r.purpose,
                intent=r.template_intent,
                language=(r.locale or fallback_language),
            )
        }
    )
    if unapproved:
        gates.append(
            _gate(
                GATE_TEMPLATE_NOT_APPROVED,
                "Meta has not approved a template for "
                + ", ".join(unapproved)
                + ". QCP refuses to send an unapproved template, and approval "
                "is Meta's to give — it typically takes days and cannot be "
                "shortened from here.",
            )
        )

    if not settings_store.delivery_enabled():
        gates.append(
            _gate(
                GATE_DELIVERY_DISABLED,
                "WhatsApp delivery is switched off platform-wide, so no "
                "product sends anything. This is the fleet kill switch plus "
                "the admin toggle; both must agree before anything leaves.",
            )
        )

    return gates


def _has_approved_template(
    db: Session, *, purpose: str, intent: str, language: str
) -> bool:
    """Is there an approved template for this intent on the *live* number?

    Scoped by account rather than by ``whatsapp_templates.product_id``, which
    is what ``routing._find_template`` does — a template lives on a number,
    and the number is chosen from the rule's purpose, not from the product.
    """
    return (
        db.query(WhatsAppTemplate.id)
        .join(WhatsAppAccount, WhatsAppAccount.id == WhatsAppTemplate.account_id)
        .filter(WhatsAppAccount.purpose == purpose)
        .filter(WhatsAppAccount.is_active == True)  # noqa: E712
        .filter(WhatsAppTemplate.intent == intent)
        .filter(WhatsAppTemplate.language == language)
        .filter(WhatsAppTemplate.status == "approved")
        .first()
        is not None
    )
