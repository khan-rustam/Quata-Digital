"""Publishers for this application's own events.

Quata Digital Enterprise (this website + admin console) is one of the six
platforms feeding @QuataAlertsBot, and it publishes through exactly the same
``emit()`` the external platforms reach over HTTP — there is no privileged
in-process shortcut. These helpers just save every call site from
reassembling the same payloads.

Everything here is best-effort: each function swallows its own errors, so a
notification problem can never fail a login, a form submission, or an admin
action.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.config import settings as env_settings

from .catalog import DEFAULT_PLATFORM
from .dispatch import emit


log = logging.getLogger("quata.notifications.local")

PLATFORM = DEFAULT_PLATFORM


# ---------------------------------------------------------------------------
# Request/user helpers
# ---------------------------------------------------------------------------

def _device_type(user_agent: Optional[str]) -> str:
    """Coarse device classification from the User-Agent.

    Deliberately crude — the alert needs "was this a phone or a laptop?",
    not browser-version fingerprinting.
    """
    ua = (user_agent or "").lower()
    if not ua:
        return "Unknown"
    if "mobile" in ua or "android" in ua or "iphone" in ua:
        return "Mobile"
    if "ipad" in ua or "tablet" in ua:
        return "Tablet"
    if "bot" in ua or "crawler" in ua or "spider" in ua:
        return "Bot"
    return "Desktop"


# Country headers set by a CDN / reverse proxy in front of the API.
# Cloudflare sends CF-IPCountry; most others use one of the rest. This is the
# only country signal available without shipping a GeoIP database — when no
# proxy sets one, country stays unknown and location comparison falls back to
# the IP network.
_COUNTRY_HEADERS = (
    "cf-ipcountry",
    "x-vercel-ip-country",
    "x-country-code",
    "x-geo-country",
)


def request_country(request: Optional[Request]) -> Optional[str]:
    """ISO country code from a trusted proxy header, if one set it."""
    if request is None:
        return None
    for header in _COUNTRY_HEADERS:
        value = (request.headers.get(header) or "").strip().upper()
        # Cloudflare uses "XX" for unknown and "T1" for Tor.
        if value and value not in {"XX", "T1"} and len(value) <= 3:
            return value
    return None


def request_context(request: Optional[Request]) -> dict:
    """IP + device + country fields common to user and security events."""
    if request is None:
        return {}
    from app.api.deps import get_client_ip

    user_agent = request.headers.get("user-agent")
    context = {
        "ip_address": get_client_ip(request),
        "device_type": _device_type(user_agent),
    }
    country = request_country(request)
    if country:
        context["country"] = country
    return context


def user_payload(user, request: Optional[Request] = None) -> dict:
    """Standard user block. Never includes anything credential-shaped."""
    payload = {
        "full_name": getattr(user, "full_name", None),
        "email": getattr(user, "email", None),
        "phone": getattr(user, "phone", None),
        "user_id": getattr(user, "id", None),
        "role": getattr(getattr(user, "role", None), "slug", None),
        "job_title": getattr(user, "job_title", None),
    }
    created = getattr(user, "created_at", None)
    if created is not None:
        payload["registration_date"] = created
    payload.update(request_context(request))
    return {k: v for k, v in payload.items() if v not in (None, "")}


def _reference_for(user) -> str:
    number = getattr(user, "employee_number", None)
    return str(number) if number else f"USR-{getattr(user, 'id', 0):06d}"


# ---------------------------------------------------------------------------
# Authentication & security
# ---------------------------------------------------------------------------

def _login_history(db: Session, user_id: int, limit: int = 50) -> list:
    from app.models import ActivityLog

    return (
        db.query(ActivityLog)
        .filter(ActivityLog.actor_id == user_id, ActivityLog.action == "login")
        .order_by(ActivityLog.id.desc())
        .limit(limit)
        .all()
    )


def _ip_network(ip: Optional[str]) -> Optional[str]:
    """First three octets of an IPv4 — a cheap "same place?" proxy.

    Not geolocation. It answers "has this account signed in from around
    here before?", which is the question the alert actually needs.
    """
    if not ip or ":" in ip:
        return ip
    parts = ip.split(".")
    return ".".join(parts[:3]) if len(parts) == 4 else ip


def admin_logged_in(db: Session, user, request: Optional[Request]) -> None:
    """Successful admin sign-in, plus new-device / new-location detection.

    Called *before* the login ActivityLog row is committed, so the history
    lookup sees only genuinely previous sessions.
    """
    try:
        payload = user_payload(user, request)
        emit(
            "security.admin_login",
            platform=PLATFORM,
            payload=payload,
            reference=_reference_for(user),
        )

        history = _login_history(db, user.id)
        if not history:
            return  # first ever login — the login alert already covers it

        user_agent = request.headers.get("user-agent") if request else None
        device = _device_type(user_agent)
        known_devices = {
            _device_type(row.user_agent) for row in history if row.user_agent
        }
        if user_agent and device not in known_devices:
            emit(
                "security.new_device_login",
                platform=PLATFORM,
                payload={**payload, "device_type": device},
                reference=_reference_for(user),
            )

        # Country when a CDN gives us one — that's the signal the security
        # brief actually asks for. Without a proxy header we fall back to
        # comparing IP networks, which answers the weaker but still useful
        # "has this account signed in from around here before?".
        current_country = payload.get("country")
        known_countries = {
            (row.details or {}).get("country")
            for row in history
            if isinstance(row.details, dict) and (row.details or {}).get("country")
        }
        if current_country and known_countries and current_country not in known_countries:
            emit(
                "security.new_location_login",
                platform=PLATFORM,
                payload={
                    **payload,
                    "location": f"New country: {current_country}",
                    "previous_countries": ", ".join(sorted(known_countries)),
                },
                reference=_reference_for(user),
            )
            return

        if current_country and known_countries:
            return  # same country, and country is the better signal — done

        current_network = _ip_network(payload.get("ip_address"))
        known_networks = {_ip_network(row.ip_address) for row in history if row.ip_address}
        if current_network and known_networks and current_network not in known_networks:
            emit(
                "security.new_location_login",
                platform=PLATFORM,
                payload={**payload, "location": f"Network {current_network}.x"},
                reference=_reference_for(user),
            )
    except Exception:  # noqa: BLE001
        log.debug("notifications.admin_logged_in_failed", exc_info=True)


def admin_logged_out(user, request: Optional[Request]) -> None:
    try:
        emit(
            "security.admin_logout",
            platform=PLATFORM,
            payload=user_payload(user, request),
            reference=_reference_for(user),
        )
    except Exception:  # noqa: BLE001
        log.debug("notifications.admin_logged_out_failed", exc_info=True)


def admin_login_failed(user, request: Optional[Request], attempts: int) -> None:
    """A wrong password against a real account.

    Escalates to 🚨 MULTIPLE FAILED LOGIN ATTEMPTS and ACCOUNT LOCKED once
    the attempt count reaches the lockout threshold.
    """
    try:
        payload = {**user_payload(user, request), "attempts": attempts}
        emit(
            "security.admin_login_failed",
            platform=PLATFORM,
            payload=payload,
            reference=_reference_for(user),
        )
        if attempts >= env_settings.MAX_LOGIN_ATTEMPTS:
            emit(
                "security.multiple_failed_logins",
                platform=PLATFORM,
                payload=payload,
                reference=_reference_for(user),
            )
            emit(
                "security.account_locked",
                platform=PLATFORM,
                payload={**payload, "locked_for": f"{env_settings.LOCKOUT_MINUTES} minutes"},
                reference=_reference_for(user),
            )
    except Exception:  # noqa: BLE001
        log.debug("notifications.admin_login_failed_failed", exc_info=True)


def suspicious_login(email: str, request: Optional[Request], reason: str) -> None:
    """A sign-in attempt against an account that doesn't exist or is closed.

    The email is reported because an administrator needs to know *what* is
    being probed; no other detail about the (non-)account is disclosed.
    """
    try:
        emit(
            "security.suspicious_login",
            platform=PLATFORM,
            payload={"email": email, "reason": reason, **request_context(request)},
            reference=email[:160],
        )
    except Exception:  # noqa: BLE001
        log.debug("notifications.suspicious_login_failed", exc_info=True)


def two_factor_changed(user, request: Optional[Request], *, enabled: bool) -> None:
    try:
        emit(
            "security.two_factor_enabled" if enabled else "security.two_factor_disabled",
            platform=PLATFORM,
            payload=user_payload(user, request),
            reference=_reference_for(user),
        )
    except Exception:  # noqa: BLE001
        log.debug("notifications.two_factor_changed_failed", exc_info=True)


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------

def user_registered(user, request: Optional[Request] = None) -> None:
    try:
        emit(
            "user.registered",
            platform=PLATFORM,
            payload=user_payload(user, request),
            reference=_reference_for(user),
        )
    except Exception:  # noqa: BLE001
        log.debug("notifications.user_registered_failed", exc_info=True)


def user_lifecycle(event_key: str, user, request: Optional[Request] = None, **extra) -> None:
    """Generic lifecycle publisher — ``user.activated``, ``user.deactivated``,
    ``user.reactivated``, ``user.deleted``, ``user.profile_updated``."""
    try:
        emit(
            event_key,
            platform=PLATFORM,
            payload={**user_payload(user, request), **extra},
            reference=_reference_for(user),
        )
    except Exception:  # noqa: BLE001
        log.debug("notifications.user_lifecycle_failed", exc_info=True)


def password_reset_requested(user, request: Optional[Request]) -> None:
    """Note: only that a reset was requested. The token never leaves email."""
    user_lifecycle("user.password_reset_requested", user, request)


def password_changed(user, request: Optional[Request], *, via: str = "self-service") -> None:
    user_lifecycle("user.password_changed", user, request, method=via)


# ---------------------------------------------------------------------------
# Website enquiries
# ---------------------------------------------------------------------------

# Contact-form reason → catalogue event, matched on a keyword *contained* in
# the submitted reason rather than on equality. The public form posts human
# labels ("Investor relations", "Customer support", "Partnerships"), and an
# exact-match table would silently route every one of them to the generic
# event. Ordered: the first keyword found wins, so put the specific ones
# first.
_CONTACT_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("investor", "website.investor_inquiry"),
    ("investment", "website.investor_inquiry"),
    ("partner", "website.partnership_request"),
    ("support", "website.support_request"),
    ("help", "website.support_request"),
    ("business", "website.business_inquiry"),
    ("sales", "website.business_inquiry"),
    ("press", "website.business_inquiry"),
    ("media", "website.business_inquiry"),
)


def contact_event_for(reason: str | None) -> str:
    """Map a contact-form reason to its catalogue event.

    Unrecognised reasons ("General enquiry", "Other", or anything a future
    form adds) fall back to the generic contact event — never dropped.
    """
    text = (reason or "").strip().lower()
    for keyword, event_key in _CONTACT_KEYWORDS:
        if keyword in text:
            return event_key
    return "website.contact_submitted"

# Partner-request path → catalogue event.
_PARTNER_EVENTS = {
    "investor": "website.investor_inquiry",
    "business": "website.business_inquiry",
    "strategic": "website.partnership_request",
    "service": "website.partnership_request",
}


def contact_submitted(payload: dict, request: Optional[Request], *, message_id: int) -> None:
    """Website contact form. Routed to the most specific event we can infer."""
    try:
        event_key = contact_event_for(payload.get("reason"))
        body = {k: v for k, v in payload.items() if k != "captcha_token"}
        emit(
            event_key,
            platform=PLATFORM,
            payload={**body, **request_context(request)},
            reference=f"MSG-{message_id:06d}",
        )
    except Exception:  # noqa: BLE001
        log.debug("notifications.contact_submitted_failed", exc_info=True)


def partner_submitted(partner_type: str, payload: dict, request: Optional[Request], *, request_id: int) -> None:
    try:
        event_key = _PARTNER_EVENTS.get(partner_type, "website.partnership_request")
        emit(
            event_key,
            platform=PLATFORM,
            payload={"partner_type": partner_type, **payload, **request_context(request)},
            reference=f"PTR-{request_id:06d}",
        )
    except Exception:  # noqa: BLE001
        log.debug("notifications.partner_submitted_failed", exc_info=True)


def career_application(
    *,
    job_title: str,
    full_name: str,
    email: str,
    phone: Optional[str],
    application_id: int,
    request: Optional[Request],
) -> None:
    try:
        emit(
            "website.career_application",
            platform=PLATFORM,
            payload={
                "full_name": full_name,
                "email": email,
                "phone": phone,
                "position": job_title,
                **request_context(request),
            },
            reference=f"APP-{application_id:06d}",
        )
    except Exception:  # noqa: BLE001
        log.debug("notifications.career_application_failed", exc_info=True)


def newsletter_subscribed(*, email: str, source: str, subscriber_id: int, request: Optional[Request]) -> None:
    try:
        emit(
            "website.newsletter_subscribed",
            platform=PLATFORM,
            payload={"email": email, "source": source, **request_context(request)},
            reference=f"SUB-{subscriber_id:06d}",
        )
    except Exception:  # noqa: BLE001
        log.debug("notifications.newsletter_subscribed_failed", exc_info=True)
