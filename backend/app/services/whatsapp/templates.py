"""Template management for QCP — reconciliation with Meta, and local CRUD.

**Meta owns the category and the status.** This module exists because QCP
originally did not know that. ``whatsapp_templates.category`` was
operator-typed data that no code path wrote and nothing ever re-asked Meta
about, so a row saying ``utility`` stayed ``utility`` here for as long as
anyone cared to look — including after Meta re-classified the template as
``MARKETING``. A marketing template sitting on the Quata Verify number is
exactly what gets a WhatsApp number restricted, and QuataFood's login OTP,
payment-PIN reset and phone-change verification have no email fallback: a
restricted Verify number locks those users out of their own accounts.

So ``sync_from_meta`` is the load-bearing function here, and three rules
shape it:

* **A sync always wins.** Category and status are overwritten from Meta on
  every reconcile. A local edit can never make a template look more sendable
  than Meta says it is.
* **An illegal pairing is data, not an exception.** The storage engine
  refuses ``category='marketing'`` on an ``account_purpose='authentication'``
  row (``ck_whatsapp_templates_marketing_never_on_verify`` and
  ``ck_whatsapp_templates_verify_is_auth_only``). When Meta reports one, the
  row is *not* written, the local row is quarantined so nothing can route to
  it, and an **alert** is returned and audited with a reason a human can act
  on. The write is additionally wrapped in a SAVEPOINT so that a constraint
  the code did not anticipate arrives as an alert rather than a 500.
* **An operator cannot approve anything.** Locally created templates land in
  ``draft`` and only a sync that finds Meta saying ``APPROVED`` can move them
  to ``approved``. Hand-approval is the same class of unvalidated-operator-
  data bug as the original hole.

A fourth rule was added after the fact, and it is about the *body*:

* **A body that asks the customer for a verification code belongs to an
  authentication template.** Redaction can key on the category, and on the
  name of a placeholder — but Meta's own templates are positional, so the
  name that reaches storage is ``"1"`` and carries nothing. A code on a
  ``utility`` template on the engagement number therefore reached
  ``whatsapp_messages.variables`` in clear, and no amount of sniffing at send
  time fixed it. The body text does not have that problem: Meta gives it to
  us, and it is written in a language a person reads. So the combination is
  refused where the template is created or synced — with a sentence, not a
  silent guess — and only *there*. Cameroon is francophone and anglophone,
  so both languages are read. Where the phrasing is ambiguous the write is
  allowed and a warning is raised instead: a false block on a legitimate
  order-update template is its own outage.

This module must never import the Meta transport — ``dispatch.py`` is the
only module allowed to (asserted by ``tests/test_whatsapp_boundaries.py``).
The provider call is therefore *injected*: ``sync_from_meta`` takes a
``fetch`` callable, and the admin route passes
``dispatch.fetch_message_templates``.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import WhatsAppAccount, WhatsAppAuditLog, WhatsAppTemplate

from . import audit


log = logging.getLogger("quata.whatsapp.templates")


PURPOSE_AUTHENTICATION = "authentication"

CATEGORY_AUTHENTICATION = "authentication"
CATEGORY_MARKETING = "marketing"
CATEGORY_UTILITY = "utility"
CATEGORIES = (CATEGORY_AUTHENTICATION, CATEGORY_MARKETING, CATEGORY_UTILITY)

STATUS_DRAFT = "draft"
STATUS_PENDING = "pending_approval"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
STATUS_PAUSED = "paused"
STATUS_DISABLED = "disabled"

# Meta's template status vocabulary → ours. Anything unrecognised maps to
# ``disabled``: an unknown status is not evidence that a template may send,
# and failing closed on it costs a re-sync rather than a restricted number.
_META_STATUS = {
    "APPROVED": STATUS_APPROVED,
    "PENDING": STATUS_PENDING,
    "IN_APPEAL": STATUS_PENDING,
    "PENDING_DELETION": STATUS_PENDING,
    "REJECTED": STATUS_REJECTED,
    "PAUSED": STATUS_PAUSED,
    "LIMIT_EXCEEDED": STATUS_PAUSED,
    "DISABLED": STATUS_DISABLED,
    "DELETED": STATUS_DISABLED,
}

# ``{{1}}`` or ``{{ order_id }}``. The captured name is what lands in
# ``variables``; Meta's authentication templates are positional, so "1" is
# the normal case and carries no meaning.
_PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}")


class TemplateRefused(Exception):
    """A write was refused for a stated, actionable reason.

    ``reason`` is a stable code the console can branch on; ``detail`` is the
    sentence an operator reads. Never a stack trace, never a 500.
    """

    def __init__(self, reason: str, detail: str, *, template_id: Optional[int] = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.detail = detail
        self.template_id = template_id


# ---------------------------------------------------------------------------
# Small pure helpers
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def body_hash(body: Optional[str]) -> Optional[str]:
    """sha256 of the approved body. Drift after a re-approval is visible."""
    if body is None:
        return None
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def placeholders(body: Optional[str]) -> list[str]:
    """The placeholder *shape*, in order of first appearance.

    Order is the contract: ``MessageSendIn.variables`` is positional and its
    arity is checked against this list by ``routing.resolve_route``.
    """
    if not body:
        return []
    seen: list[str] = []
    for name in _PLACEHOLDER.findall(body):
        if name not in seen:
            seen.append(name)
    return seen


def fingerprint(value) -> str:
    """Short, stable digest of a value — an audit trail's "old value".

    A digest, not the value: the same helper is used for every audited write
    in this module, and some of what it will one day be handed (an example
    payload) is not something to copy into a log.
    """
    blob = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


def normalise_category(raw) -> Optional[str]:
    value = str(raw or "").strip().lower()
    return value if value in CATEGORIES else None


def normalise_status(raw) -> tuple[str, bool]:
    """(local status, recognised). Unrecognised fails closed to ``disabled``."""
    value = str(raw or "").strip().upper()
    if value in _META_STATUS:
        return _META_STATUS[value], True
    return STATUS_DISABLED, False


def parse_meta_template(payload: dict) -> dict:
    """One entry of Meta's ``message_templates`` edge, in our vocabulary."""
    components = payload.get("components") or []
    body_text = None
    for component in components:
        if isinstance(component, dict) and str(component.get("type", "")).upper() == "BODY":
            body_text = component.get("text")
            break
    status, recognised = normalise_status(payload.get("status"))
    return {
        "name": str(payload.get("name") or "").strip(),
        "language": str(payload.get("language") or "en").strip() or "en",
        "category": normalise_category(payload.get("category")),
        "status": status,
        "status_recognised": recognised,
        "raw_status": str(payload.get("status") or ""),
        "raw_category": str(payload.get("category") or ""),
        "body": body_text,
        "body_hash": body_hash(body_text),
        "variables": placeholders(body_text),
        "provider_template_id": str(payload.get("id"))[:60] if payload.get("id") else None,
        "rejection_reason": (
            str(payload.get("rejected_reason") or payload.get("rejection_reason") or "")[:500]
            or None
        ),
    }


# ---------------------------------------------------------------------------
# The separation rule, stated once
# ---------------------------------------------------------------------------

def separation_problem(account_purpose: str, category: Optional[str]) -> Optional[tuple[str, str]]:
    """Why this category may not live on this account — or None.

    Mirrors the three CHECK constraints on ``whatsapp_templates``. Stated in
    Python as well as in SQL so the refusal can carry a sentence instead of
    an ``IntegrityError``.
    """
    if category is None:
        return (
            "missing_template_category",
            "Meta reported no recognisable category for this template, so it "
            "cannot be checked against the account it would sit on.",
        )
    if account_purpose == PURPOSE_AUTHENTICATION and category != CATEGORY_AUTHENTICATION:
        return (
            "non_auth_template_on_verify",
            "The Quata Verify number carries authentication templates and "
            f"nothing else. Meta classifies this template as '{category}'. "
            "Transaction and security alerts belong on QUATA as utility — "
            "move it there, or ask Meta to re-classify it, before it can be "
            "sent from the verification number.",
        )
    if category == CATEGORY_AUTHENTICATION and account_purpose != PURPOSE_AUTHENTICATION:
        return (
            "auth_template_off_verify",
            "An authentication template may only live on the Quata Verify "
            "number. Meta classifies this template as 'authentication' but it "
            "sits on the engagement number.",
        )
    return None


# ---------------------------------------------------------------------------
# The body rule: a template that asks for a code is an authentication template
#
# Everything below reads *template copy*, never a value. A template body is
# design-time text — it holds ``{{1}}``, not the code — so quoting the matched
# phrase back to the operator discloses nothing and is what makes the refusal
# actionable.
# ---------------------------------------------------------------------------

SIGNAL_BLOCK = "block"
SIGNAL_WARN = "warn"

REASON_CODE_BODY = "verification_code_body_needs_auth_category"
REASON_MAYBE_CODE_BODY = "possible_verification_code_body"

# Bodies arrive with French accents, punctuation and Meta's placeholders in
# them. Normalising to bare lowercase ASCII words means every phrase below can
# be written once and match "vérification", "Verification" and "VERIFICATION".
_ACCENTS = str.maketrans(
    "àâäáãåèéêëìíîïòóôöõùúûüçñÿ", "aaaaaaeeeeiiiiooooouuuucny"
)


def _normalise_body(body: Optional[str]) -> str:
    """Lowercase ASCII words, space-separated and space-padded.

    Placeholders are dropped rather than kept: ``{{1}}`` is not a word, and
    leaving the braces in would let ``code{{1}}`` hide from a phrase match.
    The padding is what makes ``" otp "`` a whole-word test.
    """
    text = str(body or "").lower().translate(_ACCENTS)
    text = _PLACEHOLDER.sub(" ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return f" {text.strip()} "


# Phrases that are a *code* only in the ordinary commercial sense. Removed
# from the text before anything else is looked for, so "use promo code" stops
# the bare-``code`` rule below from firing on every marketing template QCP
# will ever hold. Longest first: "code promo" must go before "code".
_BENIGN_PHRASES = (
    "promotional code", "promotion code", "promo code", "coupon code",
    "voucher code", "discount code", "referral code", "tracking code",
    "order code", "invoice code", "store code", "branch code", "gift code",
    "postal code", "post code", "zip code", "area code", "dial code",
    "country code", "currency code", "language code", "bar code", "barcode",
    "qr code", "qrcode",
    "code promotionnel", "code promo", "code de parrainage",
    "code de reduction", "code de suivi", "code postal", "code barres",
    "code barre", "code qr", "code pays", "code cadeau", "code magasin",
    "code de la commande", "code de commande", "code facture",
)

# Unambiguous. Nothing in an order update, a receipt or a campaign says any
# of these; every one of them is a customer being asked to type a secret.
_CODE_STRONG = (
    # English
    "verification code", "verification pin", "verify code",
    "one time password", "one time passcode", "one time pin", "one time code",
    "single use code", "single use password",
    "security code", "login code", "log in code", "sign in code",
    "signin code", "authentication code", "auth code", "otp",
    "2fa", "two factor", "two step verification",
    "password reset code", "pin reset code", "reset code", "pin code",
    "do not share this code", "never share this code",
    "do not share it with anyone", "this code expires", "code expires in",
    "code will expire", "enter this code", "use this code to log",
    # French
    "code de verification", "code de validation", "code de securite",
    "code de connexion", "code d authentification", "code d identification",
    "code confidentiel", "code secret", "code temporaire", "code pin",
    "code a usage unique", "mot de passe a usage unique",
    "mot de passe temporaire", "mot de passe unique",
    "code de reinitialisation", "ne partagez", "ne communiquez",
    "ne le divulguez", "ce code expire", "code expire dans",
    "saisissez ce code", "entrez ce code",
    "verification en deux etapes", "double authentification",
    "authentification a deux facteurs",
)

# Reads like a secret, but a legitimate template can say it too: "your code
# is {{1}}" is what an OTP template says *and* what a campaign says. Blocked
# on its own; downgraded to a warning when the same body also carries
# unmistakably commercial context, which is the "warn where you cannot be
# certain" half of the rule.
_CODE_LIKELY = (
    "your code is", "your pin is", "your password is", "your passcode",
    "votre code est", "votre mot de passe est", "votre code de",
    "passcode", "mot de passe",
)

_COMMERCIAL_CONTEXT = (
    "promo", "promotion", "coupon", "discount", "reduction", "voucher",
    "offer", "offre", "solde", "order", "commande", "delivery", "livraison",
    "livreur", "driver", "rider", "tracking", "suivi", "invoice", "facture",
    "receipt", "recu", "booking", "reservation", "restaurant", "menu",
    "panier", "cart", "shipping", "refund", "remboursement", "loyalty",
    "fidelite", "parrainage", "cadeau", "newsletter", "abonnement",
    "retirer", "pickup", "arrival", "arrivee",
)

# Authentication *context*, for a body that never says "code" at all.
#
# Every phrase list above keys on the noun. Meta's own authentication copy
# uses it, so they catch the templates Meta itself produces — but they catch
# nothing at all in a body an operator wrote by hand:
#
#     "Hello! Use {{1}} to finish signing in. It is valid for 5 minutes."
#
# There is no "code", no "OTP", no "password" in that sentence, and it hands
# the customer a login secret. What it does have is a placeholder standing in
# a *sign-in* sentence, and an order update never says that. So the second
# axis is the situation rather than the noun: an authentication context plus a
# placeholder is treated exactly like ``_CODE_LIKELY`` — blocked on its own,
# downgraded to a warning when the body also carries commercial context, so
# "Sign in and use promo code SOLDES25" is reported rather than refused.
_AUTH_CONTEXT = (
    # English
    "log in", "login", "logging in", "log into", "sign in", "signin",
    "signing in", "sign into", "signed in", "authenticate", "authentication",
    "verify your identity", "confirm your identity", "verify your account",
    "confirm your account", "verify your number", "verify your phone",
    "reset your password", "reset your pin", "change your password",
    "secure your account", "account recovery", "identity check",
    # French
    "connexion", "connecter", "vous connecter", "authentifier",
    "authentification", "verifier votre identite", "confirmer votre identite",
    "verifier votre compte", "confirmer votre compte",
    "verifier votre numero", "reinitialiser votre mot de passe",
    "securiser votre compte",
)

# The long tail. A bare "code"/"pin" next to a placeholder is *usually* a
# collection code or a booking reference, and blocking those would be the
# false-positive outage the brief warns about — so it is only ever a warning.
_CODE_WEAK = (
    "confirmation code", "access code", "entry code", "gate code",
    "code de confirmation", "code d acces", "code d entree",
    "code de reservation", "code", "codes", "pin",
)


def code_body_signal(body: Optional[str]) -> Optional[tuple[str, str]]:
    """``(severity, matched phrase)`` for a body that asks for a code.

    Pure and dependency-free so it can be reasoned about (and tested) on its
    own. ``None`` means the body reads like ordinary engagement copy.
    """
    text = _normalise_body(body)
    if not text.strip():
        return None
    has_placeholder = bool(_PLACEHOLDER.search(str(body or "")))
    for phrase in sorted(_BENIGN_PHRASES, key=len, reverse=True):
        padded = f" {phrase} "
        while padded in text:
            text = text.replace(padded, " ")

    for phrase in _CODE_STRONG:
        if f" {phrase} " in text:
            return (SIGNAL_BLOCK, phrase)

    commercial = any(f" {word}" in text for word in _COMMERCIAL_CONTEXT)
    for phrase in _CODE_LIKELY:
        if f" {phrase} " in text:
            return (SIGNAL_WARN if commercial else SIGNAL_BLOCK, phrase)

    # The noun-free case: a placeholder standing in a sign-in sentence.
    if has_placeholder:
        for phrase in _AUTH_CONTEXT:
            if f" {phrase} " in text:
                return (SIGNAL_WARN if commercial else SIGNAL_BLOCK, phrase)

    for phrase in _CODE_WEAK:
        if f" {phrase} " in text:
            return (SIGNAL_WARN, phrase)
    return None


def body_code_problem(
    category: Optional[str], body: Optional[str]
) -> Optional[tuple[str, str, str]]:
    """``(severity, reason, detail)`` — or None when the pairing is fine.

    An ``authentication`` template is *supposed* to carry a code, so there is
    nothing to say about one. Every other category paired with a code body is
    the combination this refuses.
    """
    if normalise_category(category) == CATEGORY_AUTHENTICATION:
        return None
    signal = code_body_signal(body)
    if signal is None:
        return None
    severity, phrase = signal
    shown = f"'{phrase}'"
    if severity == SIGNAL_BLOCK:
        return (
            SIGNAL_BLOCK,
            REASON_CODE_BODY,
            f"This template's body asks the customer for a code ({shown}), but "
            f"it is classified as '{normalise_category(category) or category}'. "
            "A template that carries a verification code must be an "
            "authentication template on the Quata Verify number — that is what "
            "keeps the code out of storage in clear and off the marketing "
            "number. Have Meta re-classify it as AUTHENTICATION, or take the "
            "code out of the body.",
        )
    return (
        SIGNAL_WARN,
        REASON_MAYBE_CODE_BODY,
        f"This template's body mentions a code ({shown}) and is not an "
        "authentication template. That is usually fine — a collection or "
        "booking reference is not a secret — but if it carries a verification "
        "code it belongs on the Quata Verify number as an authentication "
        "template. Check it.",
    )


def body_warnings(category: Optional[str], body: Optional[str]) -> list[dict]:
    """The non-blocking half of the rule, in the shape a console renders."""
    problem = body_code_problem(category, body)
    if problem is None or problem[0] != SIGNAL_WARN:
        return []
    return [{"code": problem[1], "detail": problem[2]}]


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------

def _alert(
    db: Session,
    bucket: list[dict],
    *,
    kind: str,
    account: WhatsAppAccount,
    template: str,
    language: str,
    detail: str,
    meta_category: Optional[str] = None,
    local_category: Optional[str] = None,
    template_id: Optional[int] = None,
    actor_id: Optional[int] = None,
    severity: str = "error",
) -> None:
    """Record an alert as both a returned item and an audit row.

    Returned so the sync response can put it in front of whoever pressed the
    button; audited so it is still there tomorrow when nobody did.

    ``severity`` separates "this template has been stopped" from "somebody
    should look at this". Both are alerts — an unread warning is how the
    ambiguous half of the body rule stays honest — but only the first one
    took a template out of service.
    """
    entry = {
        "kind": kind,
        "severity": severity,
        "account": account.slug,
        "account_purpose": account.purpose,
        "template": template,
        "language": language,
        "meta_category": meta_category,
        "local_category": local_category,
        "template_id": template_id,
        "detail": detail,
    }
    bucket.append(entry)
    audit.record(
        db,
        action="template.sync_alert",
        resource_type="whatsapp_template",
        resource_id=str(template_id) if template_id is not None else template,
        outcome=audit.OUTCOME_DENIED,
        reason=kind,
        actor_id=actor_id,
        account_id=account.id,
        details=entry,
    )


def _apply(row: WhatsAppTemplate, remote: dict) -> dict:
    """Write Meta's view onto a local row. Returns the fields that changed.

    Category and status are always taken from Meta — that is the whole point.
    The body-derived fields are only taken when the payload actually carried a
    body: a truncated Graph response must not silently empty a template's
    placeholder shape, because ``routing.resolve_route`` checks the caller's
    variable arity against it.
    """
    updates: list[tuple[str, object]] = [
        ("category", remote["category"]),
        ("status", remote["status"]),
        # Meta only reports a reason while the template is rejected; clearing
        # it on any other status is how a stale reason stops confusing people.
        (
            "rejection_reason",
            remote["rejection_reason"] if remote["status"] == STATUS_REJECTED else None,
        ),
    ]
    if remote["provider_template_id"]:
        updates.append(("provider_template_id", remote["provider_template_id"]))
    if remote["body"] is not None:
        updates.append(("body_hash", remote["body_hash"]))
        updates.append(("variables", remote["variables"]))

    changed: dict = {}
    for field, value in updates:
        current = getattr(row, field)
        if current != value:
            changed[field] = {"from": current, "to": value}
            setattr(row, field, value)
    row.last_synced_at = _now()
    return changed


def _quarantine(row: WhatsAppTemplate, remote: dict) -> None:
    """Meta says this template may not sit where it sits. Stop it sending.

    The category itself is deliberately *not* written — the database would
    refuse it, and the row's stated binding is the evidence of what it was
    approved as. What changes is that ``status`` leaves ``approved``, which
    is the only status ``routing._find_template`` will select.
    """
    row.status = STATUS_DISABLED
    row.last_synced_at = _now()
    if remote.get("body_hash"):
        row.body_hash = remote["body_hash"]
    if remote.get("provider_template_id"):
        row.provider_template_id = remote["provider_template_id"]


def sync_from_meta(
    db: Session,
    account: WhatsAppAccount,
    *,
    fetch: Callable[[Session, WhatsAppAccount], dict],
    actor_id: Optional[int] = None,
) -> dict:
    """Reconcile one account's templates against Meta. Meta wins.

    ``fetch`` is injected rather than imported so this module never reaches
    the transport (see the module docstring). It must return the shape
    ``dispatch.fetch_message_templates`` returns:
    ``{"ok": bool, "data": [...], "error": str | None}``.

    Never raises for a data problem. A template Meta has re-classified onto
    the wrong number comes back in ``alerts`` and is quarantined locally; a
    provider failure comes back as ``ok=False``.
    """
    alerts: list[dict] = []
    result = fetch(db, account)
    if not result.get("ok"):
        error = str(result.get("error") or "Meta rejected the request.")[:400]
        audit.record(
            db,
            action="template.sync",
            resource_type="whatsapp_account",
            resource_id=str(account.id),
            outcome=audit.OUTCOME_ERROR,
            reason=error,
            actor_id=actor_id,
            account_id=account.id,
            details={"account": account.slug},
        )
        db.commit()
        return {
            "ok": False,
            "account": account.slug,
            "error": error,
            "fetched": 0,
            "created": 0,
            "updated": 0,
            "unchanged": 0,
            "quarantined": 0,
            "alerts": alerts,
        }

    local = {
        (row.name, row.language): row
        for row in db.query(WhatsAppTemplate)
        .filter(WhatsAppTemplate.account_id == account.id)
        .all()
    }
    seen: set[tuple[str, str]] = set()
    created = updated = unchanged = quarantined = 0

    for payload in result.get("data") or []:
        if not isinstance(payload, dict):
            continue
        remote = parse_meta_template(payload)
        if not remote["name"]:
            continue
        key = (remote["name"], remote["language"])
        seen.add(key)
        row = local.get(key)

        if not remote["status_recognised"]:
            _alert(
                db,
                alerts,
                kind="unknown_status",
                account=account,
                template=remote["name"],
                language=remote["language"],
                meta_category=remote["category"],
                local_category=row.category if row else None,
                template_id=row.id if row else None,
                actor_id=actor_id,
                detail=(
                    f"Meta reported the status '{remote['raw_status']}', which "
                    "QCP does not recognise. The template has been held as "
                    "'disabled' until someone confirms what it means."
                ),
            )

        problem = separation_problem(account.purpose, remote["category"])
        if problem is not None:
            reason, detail = problem
            kind = (
                "non_auth_category_on_verify"
                if reason == "non_auth_template_on_verify"
                else reason
            )
            _alert(
                db,
                alerts,
                kind=kind,
                account=account,
                template=remote["name"],
                language=remote["language"],
                meta_category=remote["category"],
                local_category=row.category if row else None,
                template_id=row.id if row else None,
                actor_id=actor_id,
                detail=detail,
            )
            if row is not None:
                _quarantine(row, remote)
                quarantined += 1
            # A template Meta places on the wrong number is never created
            # here: the CHECK would refuse the INSERT, and a row that cannot
            # exist is not worth an exception.
            continue

        # The body rule. Meta's category can be legal for this number and the
        # body still ask the customer for a code — which is the production
        # shape of the leak, because a Meta-sourced template's placeholders
        # are numbered and tell redaction nothing. We cannot refuse Meta's
        # data, so the row is written and then held out of service.
        body_problem = body_code_problem(remote["category"], remote["body"])
        blocked_body = body_problem is not None and body_problem[0] == SIGNAL_BLOCK
        if body_problem is not None:
            _alert(
                db,
                alerts,
                kind=(
                    "verification_code_body_not_authentication"
                    if blocked_body
                    else REASON_MAYBE_CODE_BODY
                ),
                account=account,
                template=remote["name"],
                language=remote["language"],
                meta_category=remote["category"],
                local_category=row.category if row else None,
                template_id=row.id if row else None,
                actor_id=actor_id,
                severity="error" if blocked_body else "warning",
                detail=body_problem[2],
            )

        if row is None:
            row = WhatsAppTemplate(
                account_id=account.id,
                account_purpose=account.purpose,
                product_id=None,
                name=remote["name"][:120],
                language=remote["language"][:10],
                category=remote["category"],
                # Meta has no notion of our intent. The template's own name is
                # the only honest default; an admin re-points it afterwards.
                intent=remote["name"][:80],
                # A template whose body asks for a code arrives disabled, not
                # approved: ``routing._find_template`` only ever selects
                # ``approved``, so this is what stops it carrying the code.
                status=STATUS_DISABLED if blocked_body else remote["status"],
                provider_template_id=remote["provider_template_id"],
                body_hash=remote["body_hash"],
                variables=remote["variables"],
                rejection_reason=remote["rejection_reason"],
                last_synced_at=_now(),
            )
            if _write(db, row, add=True) is None:
                _alert(
                    db,
                    alerts,
                    kind="constraint_refused",
                    account=account,
                    template=remote["name"],
                    language=remote["language"],
                    meta_category=remote["category"],
                    actor_id=actor_id,
                    detail=(
                        "The database refused this template on this number. "
                        "That refusal is the account-separation invariant "
                        "doing its job — it must be reconciled by hand."
                    ),
                )
                continue
            local[key] = row
            created += 1
            if blocked_body:
                quarantined += 1
            continue

        changed = _apply(row, remote)
        if blocked_body:
            # Meta's category and body are still recorded — the row is the
            # evidence of what was approved — but the status Meta reported is
            # overridden, exactly as ``_quarantine`` does for the separation
            # case. Counted every sync, because it is still being held.
            quarantined += 1
            if row.status != STATUS_DISABLED:
                changed["status"] = {
                    "from": changed.get("status", {}).get("from", row.status),
                    "to": STATUS_DISABLED,
                }
                row.status = STATUS_DISABLED
        if _write(db, row) is None:
            _alert(
                db,
                alerts,
                kind="constraint_refused",
                account=account,
                template=remote["name"],
                language=remote["language"],
                meta_category=remote["category"],
                local_category=row.category,
                template_id=row.id,
                actor_id=actor_id,
                detail=(
                    "The database refused Meta's view of this template on this "
                    "number. The local row was left untouched and cannot be "
                    "trusted to send."
                ),
            )
            continue
        if changed:
            updated += 1
            audit.record(
                db,
                action="template.synced",
                resource_type="whatsapp_template",
                resource_id=str(row.id),
                outcome=audit.OUTCOME_OK,
                actor_id=actor_id,
                account_id=account.id,
                details={"template": row.name, "changed": changed},
            )
        else:
            unchanged += 1

    # Approved here, unknown there. Meta will reject the send, and the
    # rejection costs an attempt and a message the customer never sees.
    for (name, language), row in local.items():
        if (name, language) in seen or row.status != STATUS_APPROVED:
            continue
        _alert(
            db,
            alerts,
            kind="approved_locally_missing_at_meta",
            account=account,
            template=name,
            language=language,
            local_category=row.category,
            template_id=row.id,
            actor_id=actor_id,
            detail=(
                "This template is 'approved' in QCP but Meta's template list "
                "for this number does not contain it. Any send using it will "
                "be rejected by Meta."
            ),
        )

    audit.record(
        db,
        action="template.sync",
        resource_type="whatsapp_account",
        resource_id=str(account.id),
        outcome=audit.OUTCOME_OK if not alerts else audit.OUTCOME_DENIED,
        reason=None if not alerts else f"{len(alerts)} alert(s)",
        actor_id=actor_id,
        account_id=account.id,
        details={
            "account": account.slug,
            "created": created,
            "updated": updated,
            "unchanged": unchanged,
            "quarantined": quarantined,
            "alerts": len(alerts),
        },
    )
    db.commit()
    return {
        "ok": True,
        "account": account.slug,
        "error": None,
        "fetched": len(seen),
        "created": created,
        "updated": updated,
        "unchanged": unchanged,
        "quarantined": quarantined,
        "alerts": alerts,
    }


# ---------------------------------------------------------------------------
# The sync, on a schedule
#
# Everything above only ran when somebody pressed a button. Meta
# re-classifying a template to marketing is the exact event the two-number
# separation exists to catch, and "caught whenever someone next looks" is
# days. This is the unattended half.
#
# It follows the two patterns this repo already uses for background work —
# ``app/scripts/whatsapp_worker.py``'s cycle loop, and the idempotent
# endpoint hit from cron (``infra/cron/retention-prune.cron``). No scheduler
# is introduced: this is a function that decides for itself what is due, so
# calling it every minute and calling it hourly do the same thing.
# ---------------------------------------------------------------------------

SCHEDULED_SYNC_INTERVAL_SECONDS = 3600


def _last_sync_attempt(db: Session, account_id: int) -> Optional[datetime]:
    """When Meta was last asked about this account — success *or* failure.

    Read off the ``template.sync`` audit row rather than a new column: the
    row is already written on both outcomes, and using it means a provider
    outage costs one attempt per interval instead of one per cycle.
    """
    row = (
        db.query(WhatsAppAuditLog.created_at)
        .filter(WhatsAppAuditLog.action == "template.sync")
        .filter(WhatsAppAuditLog.account_id == account_id)
        .order_by(WhatsAppAuditLog.id.desc())
        .first()
    )
    if row is None or row[0] is None:
        return None
    stamp = row[0]
    return stamp if stamp.tzinfo is not None else stamp.replace(tzinfo=timezone.utc)


def scheduled_sync(
    db: Optional[Session] = None,
    *,
    fetch: Callable[[Session, WhatsAppAccount], dict],
    interval_seconds: int = SCHEDULED_SYNC_INTERVAL_SECONDS,
    now: Optional[datetime] = None,
    actor_id: Optional[int] = None,
) -> dict:
    """Reconcile every live account that is due. Safe on a dormant install.

    Two gates, and both of them mean "there is nothing here to sync" rather
    than "sync quietly":

    * the account must be **live** (``is_active``) — QCP ships with both
      numbers switched off, so a fresh install dials Meta zero times;
    * it must have a stored access token — asking Meta without one buys an
      error row every interval and nothing else.

    Nothing here enables anything. It cannot activate an account, enable a
    product or turn delivery on, and the only status it writes is the
    ``disabled`` that quarantining a template sets. It is deliberately *not*
    gated on ``settings_store.delivery_enabled``: catching a re-classified
    template matters most while sending is paused, not least.

    ``db`` is optional so a worker cycle can call this in one line; when it
    is omitted the session is opened and closed here.
    """
    owns_session = db is None
    if owns_session:
        from app.db.session import SessionLocal

        db = SessionLocal()
    try:
        moment = now or _now()
        cutoff = moment - timedelta(seconds=max(int(interval_seconds), 0))
        accounts = (
            db.query(WhatsAppAccount)
            .filter(WhatsAppAccount.is_active == True)  # noqa: E712
            .order_by(WhatsAppAccount.id)
            .all()
        )

        skipped: list[dict] = []
        results: list[dict] = []
        for account in accounts:
            # Presence only. The value is never read, logged or compared.
            if not account.access_token_encrypted:
                skipped.append({"account": account.slug, "reason": "no_credential"})
                continue
            last = _last_sync_attempt(db, account.id)
            if last is not None and last > cutoff:
                skipped.append({"account": account.slug, "reason": "not_due"})
                continue
            results.append(
                sync_from_meta(db, account, fetch=fetch, actor_id=actor_id)
            )

        log.info(
            "whatsapp.template_sync.scheduled",
            extra={
                "live_accounts": len(accounts),
                "synced": len(results),
                "skipped": len(skipped),
            },
        )
        return {
            "ok": True,
            "checked": len(accounts),
            "due": len(results),
            "skipped": skipped,
            "results": results,
        }
    finally:
        if owns_session:
            db.close()


def _write(db: Session, row: WhatsAppTemplate, *, add: bool = False):
    """Flush one row inside a SAVEPOINT. ``None`` means the database refused.

    The separation rules are checked in Python first, so reaching this is
    already unexpected — which is exactly why it is caught. A constraint the
    code has not anticipated must surface as an alert an operator can read,
    not as a 500 in the middle of a sync that has already written half its
    rows.
    """
    try:
        with db.begin_nested():
            if add:
                db.add(row)
            db.flush()
        return row
    except (IntegrityError, SQLAlchemyError) as exc:  # noqa: BLE001 — reported as data
        log.warning(
            "whatsapp.template_write_refused",
            extra={"template": getattr(row, "name", None), "error": type(exc).__name__},
        )
        if add and row in db:
            # Leave nothing half-added behind: the next flush in this sync
            # would otherwise retry the refused INSERT and fail the lot.
            db.expunge(row)
        return None


# ---------------------------------------------------------------------------
# Local CRUD
# ---------------------------------------------------------------------------

def _snapshot(row: WhatsAppTemplate) -> dict:
    return {
        "name": row.name,
        "language": row.language,
        "category": row.category,
        "intent": row.intent,
        "status": row.status,
        "product_id": row.product_id,
        "body_hash": row.body_hash,
        "variables": list(row.variables or []),
        "example_payload": row.example_payload or {},
    }


def create_template(
    db: Session,
    *,
    account: WhatsAppAccount,
    name: str,
    language: str,
    category: str,
    intent: str,
    body: str,
    product_id: Optional[int] = None,
    example_payload: Optional[dict] = None,
    actor_id: Optional[int] = None,
    ip_address: Optional[str] = None,
) -> WhatsAppTemplate:
    """Create a local template. It lands ``draft`` and cannot send.

    There is no ``status`` argument on purpose. A template becomes
    ``approved`` when — and only when — a sync finds Meta saying so.
    """
    category = str(category or "").strip().lower()
    if category not in CATEGORIES:
        raise TemplateRefused(
            "invalid_category",
            f"'{category}' is not one of Meta's categories "
            f"({', '.join(CATEGORIES)}).",
        )
    problem = separation_problem(account.purpose, category)
    if problem is not None:
        reason, detail = problem
        audit.record(
            db,
            action="template.create_denied",
            resource_type="whatsapp_template",
            resource_id=name,
            outcome=audit.OUTCOME_DENIED,
            reason=reason,
            actor_id=actor_id,
            account_id=account.id,
            details={"template": name, "category": category, "account": account.slug},
            ip_address=ip_address,
        )
        db.commit()
        raise TemplateRefused(reason, detail)

    # A body that asks for a code on a non-authentication template is refused
    # outright — this is the one write surface where the operator can still
    # change their mind, so it is the cheapest place to say no. Ambiguous
    # phrasing is recorded and allowed; see ``body_warnings``.
    body_problem = body_code_problem(category, body)
    if body_problem is not None:
        severity, reason, detail = body_problem
        audit.record(
            db,
            action=(
                "template.create_denied" if severity == SIGNAL_BLOCK
                else "template.body_warning"
            ),
            resource_type="whatsapp_template",
            # A warning did not deny anything, and recording it as a denial
            # would make the audit log lie about what happened.
            outcome=(
                audit.OUTCOME_DENIED if severity == SIGNAL_BLOCK else audit.OUTCOME_OK
            ),
            resource_id=name,
            reason=reason,
            actor_id=actor_id,
            account_id=account.id,
            details={"template": name, "category": category, "account": account.slug},
            ip_address=ip_address,
        )
        if severity == SIGNAL_BLOCK:
            db.commit()
            raise TemplateRefused(reason, detail)

    row = WhatsAppTemplate(
        account_id=account.id,
        account_purpose=account.purpose,
        product_id=product_id,
        name=name.strip()[:120],
        language=(language or "en").strip()[:10],
        category=category,
        intent=intent.strip()[:80],
        # Never anything else. Meta decides.
        status=STATUS_DRAFT,
        body_hash=body_hash(body),
        variables=placeholders(body),
        example_payload=example_payload or {},
        last_synced_at=None,
    )
    if _write(db, row, add=True) is None:
        db.rollback()
        raise TemplateRefused(
            "constraint_refused",
            "The database refused this template. The most likely cause is a "
            "template of the same name and language already on this number.",
        )
    audit.record(
        db,
        action="template.created",
        resource_type="whatsapp_template",
        resource_id=str(row.id),
        outcome=audit.OUTCOME_OK,
        actor_id=actor_id,
        account_id=account.id,
        details={
            "template": row.name,
            "before_fingerprint": fingerprint(None),
            "after_fingerprint": fingerprint(_snapshot(row)),
            "created": _snapshot(row),
        },
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(row)
    return row


# Fields an operator may edit. ``status`` is absent because Meta owns it, and
# ``name``/``language`` are absent because together with the account they are
# the template's identity at Meta — changing one silently orphans the row.
EDITABLE = ("intent", "product_id", "body", "example_payload", "category")


def update_template(
    db: Session,
    row: WhatsAppTemplate,
    *,
    changes: dict,
    actor_id: Optional[int] = None,
    ip_address: Optional[str] = None,
) -> WhatsAppTemplate:
    """Edit a template. Category is only editable before Meta has spoken."""
    unknown = set(changes) - set(EDITABLE)
    if unknown:
        raise TemplateRefused(
            "field_not_editable", f"Not editable here: {', '.join(sorted(unknown))}."
        )

    before = _snapshot(row)
    if "category" in changes:
        if row.last_synced_at is not None or row.status != STATUS_DRAFT:
            raise TemplateRefused(
                "category_is_owned_by_meta",
                "Meta owns this template's category. Re-run a sync to pick up "
                "a re-classification; it cannot be typed in here.",
                template_id=row.id,
            )
        category = str(changes["category"] or "").strip().lower()
        if category not in CATEGORIES:
            raise TemplateRefused(
                "invalid_category",
                f"'{category}' is not one of Meta's categories.",
                template_id=row.id,
            )
        problem = separation_problem(row.account_purpose, category)
        if problem is not None:
            reason, detail = problem
            audit.record(
                db,
                action="template.update_denied",
                resource_type="whatsapp_template",
                resource_id=str(row.id),
                outcome=audit.OUTCOME_DENIED,
                reason=reason,
                actor_id=actor_id,
                account_id=row.account_id,
                details={"template": row.name, "category": category},
                ip_address=ip_address,
            )
            db.commit()
            raise TemplateRefused(reason, detail, template_id=row.id)
        row.category = category

    # Same rule as ``create_template``, against whichever category the edit
    # leaves in place. Without this, "create it clean, then edit the code in"
    # is a one-request way round the whole guard.
    if changes.get("body") is not None:
        body_problem = body_code_problem(row.category, changes["body"])
        if body_problem is not None and body_problem[0] == SIGNAL_BLOCK:
            _, reason, detail = body_problem
            audit.record(
                db,
                action="template.update_denied",
                resource_type="whatsapp_template",
                resource_id=str(row.id),
                outcome=audit.OUTCOME_DENIED,
                reason=reason,
                actor_id=actor_id,
                account_id=row.account_id,
                details={"template": row.name, "category": row.category},
                ip_address=ip_address,
            )
            db.commit()
            raise TemplateRefused(reason, detail, template_id=row.id)

    if "intent" in changes and changes["intent"] is not None:
        row.intent = str(changes["intent"]).strip()[:80]
    if "product_id" in changes:
        row.product_id = changes["product_id"]
    if "example_payload" in changes and changes["example_payload"] is not None:
        row.example_payload = changes["example_payload"]
    if "body" in changes and changes["body"] is not None:
        row.body_hash = body_hash(changes["body"])
        row.variables = placeholders(changes["body"])

    if _write(db, row) is None:
        db.rollback()
        raise TemplateRefused(
            "constraint_refused",
            "The database refused this edit.",
            template_id=row.id,
        )
    after = _snapshot(row)
    changed = {
        field: {"from": before[field], "to": after[field]}
        for field in after
        if before[field] != after[field]
    }
    audit.record(
        db,
        action="template.updated",
        resource_type="whatsapp_template",
        resource_id=str(row.id),
        outcome=audit.OUTCOME_OK,
        actor_id=actor_id,
        account_id=row.account_id,
        details={
            "template": row.name,
            "before_fingerprint": fingerprint(before),
            "after_fingerprint": fingerprint(after),
            "changed": changed,
        },
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(row)
    return row


def retire_template(
    db: Session,
    row: WhatsAppTemplate,
    *,
    actor_id: Optional[int] = None,
    ip_address: Optional[str] = None,
) -> WhatsAppTemplate:
    """Take a template out of service. The row stays; the send path stops.

    Nothing is deleted — ``routing._find_template`` only ever selects
    ``approved``, so ``disabled`` is enough to stop it, and the history of
    what was once approved on which number is evidence worth keeping.
    """
    before = _snapshot(row)
    row.status = STATUS_DISABLED
    db.flush()
    audit.record(
        db,
        action="template.retired",
        resource_type="whatsapp_template",
        resource_id=str(row.id),
        outcome=audit.OUTCOME_OK,
        actor_id=actor_id,
        account_id=row.account_id,
        details={
            "template": row.name,
            "before_fingerprint": fingerprint(before),
            "after_fingerprint": fingerprint(_snapshot(row)),
            "changed": {"status": {"from": before["status"], "to": STATUS_DISABLED}},
        },
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(row)
    return row


def recent_alerts(db: Session, *, limit: int = 50) -> list[dict]:
    """The outstanding sync alerts, newest first.

    Read straight off the audit log rather than a second table: an alert that
    lives only in an HTTP response is an alert nobody sees on Monday.

    The stored ``details`` are flattened up so an item here has the **same
    shape** as an entry in a sync response's ``alerts``. That is the whole
    point of this endpoint: the sync that found the problem may have been run
    by someone else days ago, so this list has to name the same three things —
    which template, on which number, and why. Returned nested, the console
    could only render the row's id.
    """
    rows = (
        db.query(WhatsAppAuditLog)
        .filter(WhatsAppAuditLog.action == "template.sync_alert")
        .order_by(WhatsAppAuditLog.id.desc())
        .limit(limit)
        .all()
    )
    items = []
    for row in rows:
        details = dict(row.details or {})
        items.append(
            {
                **details,
                # The audit row is authoritative for these three: ``kind`` is
                # the stored reason, and the id/timestamp only exist here.
                "id": row.id,
                "kind": row.reason or details.get("kind"),
                "resource_id": row.resource_id,
                "account_id": row.account_id,
                "created_at": row.created_at,
            }
        )
    return items
