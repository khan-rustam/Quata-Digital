"""QCP — the admin console's **write** surface for templates and routing.

``routes_admin_whatsapp.py`` is deliberately read-only. That left QCP with no
way to create a template or a routing rule at all, so an engineer inserted
rows by hand — which is how ``whatsapp_templates.category`` came to be
operator-typed data that nothing validated, and how a utility template could
end up on the Quata Verify number with nobody able to see it. This module is
the fix: every write goes through a service that states the separation rules
in Python, refuses a violation with a reason a human can act on, and audits
the attempt either way.

Four rules shape it, and each is asserted by
``tests/test_whatsapp_templates.py``.

**No secret is ever returned.** Nothing in here reads a credential column at
all — not the encrypted account secrets, not the product key hash. The shapes
below carry template and routing metadata and nothing else.

**Meta owns approval.** No request body accepts ``status``; the models forbid
extra fields, so an attempt to send one is a 422 rather than a silently
ignored key. A template becomes ``approved`` only when a sync finds Meta
saying so.

**Refusals are refusals, not 500s.** ``TemplateRefused`` and ``RuleRefused``
become ``409`` with ``{"reason": <stable code>, "detail": <sentence>}``. A
sync that finds a re-classified template on Verify returns ``200`` with the
alert in the body — the database refused the row, and that refusal is data.

**Nothing here switches QCP on.** New templates land ``draft``, new routing
rules land inactive, and no route touches ``whatsapp_accounts.is_active``,
``whatsapp_products.is_enabled`` or the delivery setting.
"""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models import (
    User,
    WhatsAppAccount,
    WhatsAppProduct,
    WhatsAppRoutingRule,
    WhatsAppTemplate,
)
from app.services.whatsapp import dispatch as dispatch_service
from app.services.whatsapp import registry as registry_service
from app.services.whatsapp import templates as templates_service


router = APIRouter(tags=["whatsapp-admin"])

PERM = "settings:manage"


# ---------------------------------------------------------------------------
# Request models — every one of them forbids extra fields
# ---------------------------------------------------------------------------

class TemplateCreateIn(BaseModel):
    """A locally drafted template.

    There is no ``status`` field and there never will be. Meta decides.
    """

    model_config = ConfigDict(extra="forbid")

    account: str = Field(..., min_length=1, max_length=40)
    name: str = Field(..., min_length=1, max_length=120)
    language: str = Field(default="en", max_length=10)
    category: Literal["authentication", "marketing", "utility"]
    intent: str = Field(..., min_length=1, max_length=80)
    body: str = Field(..., min_length=1, max_length=4096)
    product: Optional[str] = Field(default=None, max_length=40)
    example_payload: Optional[dict] = None


class TemplateUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Optional[str] = Field(default=None, min_length=1, max_length=80)
    body: Optional[str] = Field(default=None, min_length=1, max_length=4096)
    product: Optional[str] = Field(default=None, max_length=40)
    example_payload: Optional[dict] = None
    # Only honoured while the template is a local draft Meta has never seen.
    category: Optional[Literal["authentication", "marketing", "utility"]] = None


class RuleCreateIn(BaseModel):
    """A routing rule. ``is_active`` is absent: new rules take no traffic."""

    model_config = ConfigDict(extra="forbid")

    product: str = Field(..., min_length=1, max_length=40)
    intent: str = Field(..., min_length=1, max_length=80)
    purpose: Literal["authentication", "engagement"]
    template_intent: str = Field(..., min_length=1, max_length=80)
    locale: Optional[str] = Field(default=None, max_length=10)
    priority: int = Field(default=100, ge=0, le=10000)
    fallback_channel: Optional[Literal["email", "sms", "none"]] = None


class RuleUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purpose: Optional[Literal["authentication", "engagement"]] = None
    template_intent: Optional[str] = Field(default=None, min_length=1, max_length=80)
    locale: Optional[str] = Field(default=None, max_length=10)
    priority: Optional[int] = Field(default=None, ge=0, le=10000)
    fallback_channel: Optional[Literal["email", "sms", "none"]] = None


# ---------------------------------------------------------------------------
# Shared plumbing
# ---------------------------------------------------------------------------

def _ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


def _refused(exc) -> HTTPException:
    """A stated refusal, as a 409 the console can branch on."""
    payload = {"reason": exc.reason, "detail": exc.detail}
    problems = getattr(exc, "problems", None)
    if problems:
        payload["problems"] = problems
    return HTTPException(status.HTTP_409_CONFLICT, payload)


def _account(db: Session, slug: str) -> WhatsAppAccount:
    row = db.query(WhatsAppAccount).filter(WhatsAppAccount.slug == slug).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown account '{slug}'")
    return row


def _product(db: Session, slug: str) -> WhatsAppProduct:
    row = db.query(WhatsAppProduct).filter(WhatsAppProduct.slug == slug).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown product '{slug}'")
    return row


def _template_out(
    row: WhatsAppTemplate,
    *,
    account_slug: Optional[str] = None,
    warnings: Optional[list] = None,
) -> dict:
    return {
        "id": row.id,
        # Non-blocking findings about the body — the "we cannot be certain,
        # so look at it" half of the verification-code rule. Always present
        # so the console never has to test for the key.
        "warnings": warnings or [],
        "name": row.name,
        "language": row.language,
        "category": row.category,
        "intent": row.intent,
        "status": row.status,
        "account_id": row.account_id,
        "account": account_slug,
        "account_purpose": row.account_purpose,
        "product_id": row.product_id,
        "variables": list(row.variables or []),
        "example_payload": row.example_payload or {},
        "provider_template_id": row.provider_template_id,
        "body_hash": row.body_hash,
        "rejection_reason": row.rejection_reason,
        "last_synced_at": row.last_synced_at,
        "created_at": row.created_at,
    }


# ---------------------------------------------------------------------------
# Template sync — the root-cause fix
# ---------------------------------------------------------------------------

@router.post("/admin/qcp/accounts/{slug}/templates/sync")
def qcp_sync_templates(
    slug: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM)),
):
    """Reconcile one account's templates against Meta. Meta wins.

    The provider call is ``dispatch.fetch_message_templates`` — the sanctioned
    (and only) path to the Graph API — passed in rather than imported by the
    service, so the "one module talks to Meta" boundary holds.

    A template Meta has re-classified onto the wrong number comes back in
    ``alerts`` with a ``200``: the database refuses the row, the local row is
    quarantined so nothing can route to it, and a human is told why. That is
    the single most valuable thing this endpoint does.
    """
    account = _account(db, slug)
    result = templates_service.sync_from_meta(
        db,
        account,
        fetch=dispatch_service.fetch_message_templates,
        actor_id=user.id,
    )
    return result


@router.post("/admin/qcp/templates/sync-due")
def qcp_sync_due_templates(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM)),
):
    """Reconcile every live account that has not been reconciled recently.

    This is the unattended path, and it exists because nothing else was one:
    a sync only happened when a person clicked, so Meta re-classifying a
    template to marketing — the exact event the two-number separation exists
    to catch — was caught whenever someone next looked, which could be days.

    It is idempotent and interval-gated, so it is safe on the repo's existing
    cron pattern (see ``infra/cron/retention-prune.cron``) at any frequency::

        */15 * * * * curl -fsS -X POST \\
            https://api.quatadigital.com/api/v1/admin/qcp/templates/sync-due \\
            -H "Authorization: Bearer $ADMIN_TOKEN"

    On a dormant install both numbers are inactive, so this does nothing at
    all — and it can enable nothing: the only status it writes is the
    ``disabled`` that quarantining a template sets.
    """
    return templates_service.scheduled_sync(
        db, fetch=dispatch_service.fetch_message_templates, actor_id=user.id
    )


@router.get("/admin/qcp/templates/alerts")
def qcp_template_alerts(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM)),
):
    """Outstanding sync alerts, newest first, read off the audit log."""
    return {"items": templates_service.recent_alerts(db, limit=limit)}


# ---------------------------------------------------------------------------
# Template CRUD
# ---------------------------------------------------------------------------

@router.post("/admin/qcp/templates", status_code=status.HTTP_201_CREATED)
def qcp_create_template(
    request: Request,
    payload: TemplateCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM)),
):
    """Draft a template locally. It cannot send until a sync approves it."""
    account = _account(db, payload.account)
    product = _product(db, payload.product) if payload.product else None
    try:
        row = templates_service.create_template(
            db,
            account=account,
            name=payload.name,
            language=payload.language,
            category=payload.category,
            intent=payload.intent,
            body=payload.body,
            product_id=product.id if product else None,
            example_payload=payload.example_payload,
            actor_id=user.id,
            ip_address=_ip(request),
        )
    except templates_service.TemplateRefused as exc:
        raise _refused(exc) from exc
    return _template_out(
        row,
        account_slug=account.slug,
        warnings=templates_service.body_warnings(payload.category, payload.body),
    )


@router.patch("/admin/qcp/templates/{template_id}")
def qcp_update_template(
    template_id: int,
    request: Request,
    payload: TemplateUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM)),
):
    row = db.get(WhatsAppTemplate, template_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found")

    changes = payload.model_dump(exclude_unset=True)
    if "product" in changes:
        slug = changes.pop("product")
        changes["product_id"] = _product(db, slug).id if slug else None
    try:
        row = templates_service.update_template(
            db, row, changes=changes, actor_id=user.id, ip_address=_ip(request)
        )
    except templates_service.TemplateRefused as exc:
        raise _refused(exc) from exc
    account = db.get(WhatsAppAccount, row.account_id)
    return _template_out(
        row,
        account_slug=account.slug if account else None,
        warnings=(
            templates_service.body_warnings(row.category, payload.body)
            if payload.body is not None
            else []
        ),
    )


@router.post("/admin/qcp/templates/{template_id}/retire")
def qcp_retire_template(
    template_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM)),
):
    """Take a template out of service. Nothing is deleted."""
    row = db.get(WhatsAppTemplate, template_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found")
    row = templates_service.retire_template(
        db, row, actor_id=user.id, ip_address=_ip(request)
    )
    account = db.get(WhatsAppAccount, row.account_id)
    return _template_out(row, account_slug=account.slug if account else None)


# ---------------------------------------------------------------------------
# Routing rules
#
# ``/coverage`` is declared before ``/{rule_id}`` so the literal path is not
# swallowed by the parameterised one.
# ---------------------------------------------------------------------------

@router.get("/admin/qcp/routing-rules/coverage")
def qcp_routing_coverage(
    product: str = Query(..., max_length=40),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM)),
):
    """Where this product's routing has holes."""
    return registry_service.coverage(db, _product(db, product))


@router.get("/admin/qcp/routing-rules")
def qcp_list_routing_rules(
    product: Optional[str] = Query(default=None, max_length=40),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM)),
):
    # The whole product row, not just its slug: ``rule_out`` needs
    # ``allowed_purposes`` to tell a live rule from one the world has left
    # behind, and a rule shown as live when it can carry nothing is the
    # console telling the operator something untrue.
    products = {p.id: p for p in db.query(WhatsAppProduct).all()}
    query = db.query(WhatsAppRoutingRule)
    if product:
        query = query.filter(WhatsAppRoutingRule.product_id == _product(db, product).id)
    rows = query.order_by(
        WhatsAppRoutingRule.product_id,
        WhatsAppRoutingRule.intent,
        WhatsAppRoutingRule.priority,
    ).all()
    return {
        "items": [
            registry_service.rule_out(r, product=products.get(r.product_id))
            for r in rows
        ]
    }


@router.post("/admin/qcp/routing-rules", status_code=status.HTTP_201_CREATED)
def qcp_create_routing_rule(
    request: Request,
    payload: RuleCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM)),
):
    """Create a rule. It lands inactive; switching it on is a separate act."""
    product = _product(db, payload.product)
    try:
        rule, problems = registry_service.create_rule(
            db,
            product=product,
            intent=payload.intent,
            purpose=payload.purpose,
            template_intent=payload.template_intent,
            locale=payload.locale,
            priority=payload.priority,
            fallback_channel=payload.fallback_channel,
            actor_id=user.id,
            ip_address=_ip(request),
        )
    except registry_service.RuleRefused as exc:
        raise _refused(exc) from exc
    out = registry_service.rule_out(rule, product=product)
    out["problems"] = problems
    return out


@router.patch("/admin/qcp/routing-rules/{rule_id}")
def qcp_update_routing_rule(
    rule_id: int,
    request: Request,
    payload: RuleUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM)),
):
    rule = db.get(WhatsAppRoutingRule, rule_id)
    if rule is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Routing rule not found")
    product = db.get(WhatsAppProduct, rule.product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Routing rule has no product")
    try:
        rule, problems = registry_service.update_rule(
            db,
            rule,
            changes=payload.model_dump(exclude_unset=True),
            product=product,
            actor_id=user.id,
            ip_address=_ip(request),
        )
    except registry_service.RuleRefused as exc:
        raise _refused(exc) from exc
    out = registry_service.rule_out(rule, product=product)
    out["problems"] = problems
    return out


@router.post("/admin/qcp/routing-rules/{rule_id}/activate")
def qcp_activate_routing_rule(
    rule_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM)),
):
    """Switch a rule on. Every guard is re-run — the world has moved."""
    return _set_active(db, rule_id, True, user, request)


@router.post("/admin/qcp/routing-rules/{rule_id}/deactivate")
def qcp_deactivate_routing_rule(
    rule_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM)),
):
    """Switch a rule off. Never refused — stopping traffic must always work."""
    return _set_active(db, rule_id, False, user, request)


def _set_active(db: Session, rule_id: int, active: bool, user: User, request: Request) -> dict:
    rule = db.get(WhatsAppRoutingRule, rule_id)
    if rule is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Routing rule not found")
    product = db.get(WhatsAppProduct, rule.product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Routing rule has no product")
    try:
        rule, problems = registry_service.set_active(
            db,
            rule,
            active=active,
            product=product,
            actor_id=user.id,
            ip_address=_ip(request),
        )
    except registry_service.RuleRefused as exc:
        raise _refused(exc) from exc
    out = registry_service.rule_out(rule, product=product)
    out["problems"] = problems
    return out


@router.delete("/admin/qcp/routing-rules/{rule_id}")
def qcp_delete_routing_rule(
    rule_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM)),
):
    rule = db.get(WhatsAppRoutingRule, rule_id)
    if rule is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Routing rule not found")
    deleted = registry_service.delete_rule(
        db, rule, actor_id=user.id, ip_address=_ip(request)
    )
    return {"deleted": True, "id": rule_id, "was": deleted}
