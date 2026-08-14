"""QCP campaigns — the admin console's read and write surface.

The product-facing gateway (``routes_whatsapp.py``) has no campaign routes and
must not gain any: a campaign messages thousands of people at once on the
number that carries the fleet's login codes, and that is an operator's
decision made in a console, not an API call a product can make with its
gateway key.

**Two permissions, split the way the rest of QCP splits them.** Drafting,
editing, previewing an audience and reading results take ``settings:manage``
— the same ticket that gates the templates and routing screens. Two routes
take ``whatsapp:operate`` instead: **start** and **schedule**. Those are the
acts that put marketing traffic on the shared engagement number, which is the
same class of decision as switching a number on or minting a product key, and
"can edit site settings" is not that claim.

**Stop deliberately takes the lower permission.** Anyone who can see a
campaign can halt it. A stop button that asks for a permission the person
watching the disaster does not hold is not a stop button, and stopping is
always the safe direction — it can only reduce what QCP sends.

**Nothing here switches QCP on.** No route touches
``whatsapp_accounts.is_active``, ``whatsapp_products.is_enabled`` or the
delivery setting. ``POST /start`` *refuses* while delivery is off rather than
enabling it; that refusal is the ship-inert rule, stated where an operator
will meet it.

**Refusals are refusals, not 500s.** ``CampaignRefused`` becomes a ``409``
with ``{"reason": <stable code>, "detail": <sentence>}`` — the same shape
``routes_admin_templates.py`` uses, so the console's ``explainQcpRefusal``
renders it with no new branch.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, require_permission
from app.db.session import get_db
from app.models import User, WhatsAppProduct
from app.services.whatsapp import campaigns


router = APIRouter(tags=["whatsapp-admin"])

# Read, draft, edit, preview. The console permission every Admin holds.
PERM = "settings:manage"

# Arm the send. Two routes only:
#
#   POST /admin/qcp/campaigns/{uid}/start
#   POST /admin/qcp/campaigns/{uid}/schedule
#
# These name **only** this permission: ``require_permission`` is an OR over
# the names it is given, so listing ``PERM`` alongside would make the split
# decorative. The one bypass is ``*``, which ``deps.user_permissions`` grants
# the ``super_admin`` role.
PERM_OPERATE = "whatsapp:operate"


# ---------------------------------------------------------------------------
# Request models — every one forbids extra fields
# ---------------------------------------------------------------------------

class CampaignCreateIn(BaseModel):
    """A drafted campaign.

    There is no ``status`` field and there never will be: a campaign is
    created as a draft, and starting it is a separate act with a separate
    permission. There is no ``account`` field either — a campaign goes out on
    the engagement number or it does not go out, so there is nothing to
    choose.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=120)
    product: str = Field(..., min_length=1, max_length=40)
    intent: str = Field(..., min_length=1, max_length=80)
    locale: Optional[str] = Field(default=None, max_length=10)
    audience_source: str = Field(..., min_length=1, max_length=30)
    audience_filters: Optional[dict] = None
    variables: Optional[list[str]] = None
    messages_per_minute: Optional[int] = Field(default=None, ge=1, le=60)


class CampaignUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    intent: Optional[str] = Field(default=None, min_length=1, max_length=80)
    locale: Optional[str] = Field(default=None, max_length=10)
    audience_source: Optional[str] = Field(default=None, max_length=30)
    audience_filters: Optional[dict] = None
    variables: Optional[list[str]] = None
    messages_per_minute: Optional[int] = Field(default=None, ge=1, le=60)


class AudiencePreviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product: str = Field(..., min_length=1, max_length=40)
    audience_source: str = Field(..., min_length=1, max_length=30)
    audience_filters: Optional[dict] = None


class ScheduleIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scheduled_at: datetime


class StopIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Optional[str] = Field(default=None, max_length=200)


class OptOutIn(BaseModel):
    """Record that a customer has asked to stop.

    ``source`` is not settable. An opt-out recorded through the console is an
    ``admin`` opt-out, and an ``inbound_keyword`` one is the customer's own
    word — letting a form claim to be the customer would put a fact into the
    audit trail that nobody said.
    """

    model_config = ConfigDict(extra="forbid")

    phone_e164: str = Field(..., min_length=4, max_length=24)
    note: Optional[str] = Field(default=None, max_length=200)


class PauseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Optional[str] = Field(default=None, max_length=200)


# ---------------------------------------------------------------------------
# Shared plumbing
# ---------------------------------------------------------------------------

def _refused(exc) -> HTTPException:
    """A stated refusal, as the 409 shape the console already understands."""
    return HTTPException(
        status.HTTP_409_CONFLICT, {"reason": exc.reason, "detail": exc.detail}
    )


def _product(db: Session, slug: str) -> WhatsAppProduct:
    row = db.query(WhatsAppProduct).filter(WhatsAppProduct.slug == slug).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown product '{slug}'")
    return row


def _campaign(db: Session, campaign_uid: str):
    row = campaigns.service.get(db, campaign_uid)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")
    return row


# ---------------------------------------------------------------------------
# Opt-outs. Declared before /{campaign_uid} so the literal path wins.
# ---------------------------------------------------------------------------

@router.get("/admin/qcp/campaigns/opt-outs")
def qcp_opt_outs(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM)),
):
    """Everyone who has asked not to be messaged. Newest first."""
    return {"items": campaigns.consent.recent(db, limit=limit), "total": campaigns.consent.count(db)}


@router.post("/admin/qcp/campaigns/opt-outs", status_code=status.HTTP_201_CREATED)
def qcp_record_opt_out(
    request: Request,
    payload: OptOutIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM)),
):
    """Record an opt-out somebody gave outside WhatsApp — by phone, in person.

    There is no route that removes one. See ``consent``.
    """
    row, created = campaigns.consent.record(
        db,
        payload.phone_e164.strip(),
        source="admin",
        note=payload.note,
        actor_id=user.id,
        ip_address=get_client_ip(request),
    )
    db.commit()
    if row is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "A phone number is required")
    return {
        "phone_e164": row.phone_e164,
        "source": row.source,
        "created": created,
        "note": row.note,
    }


@router.post("/admin/qcp/campaigns/opt-outs/scan")
def qcp_scan_opt_outs(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM)),
):
    """Read stored inbound messages and honour every STOP found in them.

    The campaign runner already does this before every batch; this route
    exists so an operator can run it on demand, and so the count is visible
    before a campaign is started rather than only after.
    """
    from datetime import timedelta, timezone

    since = datetime.now(timezone.utc) - timedelta(days=days)
    result = campaigns.consent.sweep(db, since=since)
    db.commit()
    return result


# ---------------------------------------------------------------------------
# The tick
# ---------------------------------------------------------------------------

@router.post("/admin/qcp/campaigns/run-due")
def qcp_run_due(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_OPERATE)),
):
    """Promote scheduled campaigns that are due, then send one paced batch each.

    Idempotent at any interval — the pace lives on the campaign row, not in
    the caller. On a dormant install this promotes nothing and sends nothing.
    """
    return campaigns.runner.run_due(db)


# ---------------------------------------------------------------------------
# Audience preview — before a campaign exists
# ---------------------------------------------------------------------------

@router.post("/admin/qcp/campaigns/audience-preview")
def qcp_preview_audience(
    payload: AudiencePreviewIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM)),
):
    """How many people this audience would reach. Writes nothing, sends nothing."""
    product = _product(db, payload.product)
    account = campaigns.service.engagement_account(db)
    if account is None:
        raise _refused(
            campaigns.CampaignRefused(
                "no_account_for_purpose",
                "There is no live QUATA number, so there is no audience to "
                "build. Campaigns only exist on the engagement number.",
            )
        )
    try:
        return campaigns.audience.preview(
            db,
            source=payload.audience_source,
            filters=payload.audience_filters,
            account_id=account.id,
            product=product,
        )
    except campaigns.audience.AudienceRefused as exc:
        raise _refused(exc) from exc


# ---------------------------------------------------------------------------
# Campaign CRUD
# ---------------------------------------------------------------------------

@router.get("/admin/qcp/campaigns")
def qcp_list_campaigns(
    campaign_status: Optional[str] = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM)),
):
    """Every campaign, plus why one can or cannot be started right now.

    ``platform`` is carried on the list response rather than left to a second
    call, because "no campaigns" and "no campaign can send" are different
    states and an empty screen has to be able to say which it is looking at.
    """
    try:
        rows = campaigns.service.listing(db, status=campaign_status, limit=limit)
    except campaigns.CampaignRefused as exc:
        raise _refused(exc) from exc
    return {
        "items": [campaigns.service.campaign_out(db, row) for row in rows],
        "platform": campaigns.service.platform_state(db),
    }


@router.post("/admin/qcp/campaigns", status_code=status.HTTP_201_CREATED)
def qcp_create_campaign(
    request: Request,
    payload: CampaignCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM)),
):
    """Draft a campaign. It lands ``draft`` and sends nothing."""
    product = _product(db, payload.product)
    try:
        row = campaigns.service.create(
            db,
            name=payload.name,
            product=product,
            intent=payload.intent,
            locale=payload.locale,
            audience_source=payload.audience_source,
            audience_filters=payload.audience_filters,
            variables=payload.variables,
            messages_per_minute=payload.messages_per_minute,
            actor_id=user.id,
            ip_address=get_client_ip(request),
        )
    except campaigns.CampaignRefused as exc:
        db.rollback()
        raise _refused(exc) from exc
    db.commit()
    return campaigns.service.campaign_out(db, row)


@router.get("/admin/qcp/campaigns/{campaign_uid}")
def qcp_get_campaign(
    campaign_uid: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM)),
):
    row = _campaign(db, campaign_uid)
    return {
        **campaigns.service.campaign_out(db, row),
        "recipients": campaigns.service.recipients(db, row, limit=100),
    }


@router.patch("/admin/qcp/campaigns/{campaign_uid}")
def qcp_update_campaign(
    campaign_uid: str,
    request: Request,
    payload: CampaignUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM)),
):
    row = _campaign(db, campaign_uid)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return campaigns.service.campaign_out(db, row)
    try:
        campaigns.service.update(
            db,
            row,
            changes=changes,
            actor_id=user.id,
            ip_address=get_client_ip(request),
        )
    except campaigns.CampaignRefused as exc:
        db.rollback()
        raise _refused(exc) from exc
    db.commit()
    return campaigns.service.campaign_out(db, row)


@router.post("/admin/qcp/campaigns/{campaign_uid}/audience")
def qcp_build_audience(
    campaign_uid: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM)),
):
    """Materialise the recipient list from the campaign's filters.

    Destructive and repeatable: the previous list is discarded so what is on
    screen is always what the current filters produce. Opt-outs are removed
    here and checked again before every individual send.
    """
    row = _campaign(db, campaign_uid)
    try:
        result = campaigns.service.build_audience(
            db, row, actor_id=user.id, ip_address=get_client_ip(request)
        )
    except campaigns.CampaignRefused as exc:
        db.rollback()
        raise _refused(exc) from exc
    db.commit()
    return {**result, "campaign": campaigns.service.campaign_out(db, row)}


# ---------------------------------------------------------------------------
# The switches
# ---------------------------------------------------------------------------

@router.post("/admin/qcp/campaigns/{campaign_uid}/schedule")
def qcp_schedule_campaign(
    campaign_uid: str,
    request: Request,
    payload: ScheduleIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_OPERATE)),
):
    """Arm a campaign for a future time. Still sends nothing by itself."""
    row = _campaign(db, campaign_uid)
    try:
        campaigns.service.schedule(
            db,
            row,
            when=payload.scheduled_at,
            actor_id=user.id,
            ip_address=get_client_ip(request),
        )
    except campaigns.CampaignRefused as exc:
        db.rollback()
        raise _refused(exc) from exc
    db.commit()
    return campaigns.service.campaign_out(db, row)


@router.post("/admin/qcp/campaigns/{campaign_uid}/start")
def qcp_start_campaign(
    campaign_uid: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_OPERATE)),
):
    """Begin sending, at the campaign's pace.

    Refused while QCP is dormant. That refusal is the whole ship-inert
    contract: the environment kill switch and the admin toggle must both say
    yes, and this route will not turn either of them on for you.
    """
    row = _campaign(db, campaign_uid)
    try:
        campaigns.service.start(
            db, row, actor_id=user.id, ip_address=get_client_ip(request)
        )
    except campaigns.CampaignRefused as exc:
        db.rollback()
        raise _refused(exc) from exc
    db.commit()
    return campaigns.service.campaign_out(db, row)


@router.post("/admin/qcp/campaigns/{campaign_uid}/pause")
def qcp_pause_campaign(
    campaign_uid: str,
    request: Request,
    payload: PauseIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM)),
):
    """Hold the send. Recipients stay pending; the campaign can be resumed."""
    row = _campaign(db, campaign_uid)
    try:
        campaigns.service.pause(
            db,
            row,
            actor_id=user.id,
            reason=payload.reason,
            ip_address=get_client_ip(request),
        )
    except campaigns.CampaignRefused as exc:
        db.rollback()
        raise _refused(exc) from exc
    db.commit()
    return campaigns.service.campaign_out(db, row)


@router.post("/admin/qcp/campaigns/{campaign_uid}/stop")
def qcp_stop_campaign(
    campaign_uid: str,
    request: Request,
    payload: StopIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM)),
):
    """Halt a campaign for good, now.

    Takes ``settings:manage``, not ``whatsapp:operate``: everyone who can see
    a campaign can stop it. Stopping already-stopped is a 200, not an error —
    the person clicking twice is the person who most needs it to work.
    """
    row = _campaign(db, campaign_uid)
    result = campaigns.service.stop(
        db,
        row,
        actor_id=user.id,
        reason=payload.reason,
        ip_address=get_client_ip(request),
    )
    db.commit()
    return {**result, "campaign": campaigns.service.campaign_out(db, row)}
