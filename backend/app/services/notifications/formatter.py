"""Renders an event into the standard @QuataAlertsBot message.

Every notification from every platform comes out in the same shape, so an
administrator reads the first three lines and already knows what happened
and how much it matters:

    🔔 QUATA ALERT

    Platform:
    QuataPay

    Priority:
    🟢 INFO

    Event:
    New User Registration

    Status:
    SUCCESS

    …event-specific fields…

    Reference:
    USR-000245

    Date:
    25 Jul 2026

    Time:
    14:30

Priority sits directly under Platform so severity is readable before the
event name — on a phone lock screen that's often all you get. The emoji
signal lives there and only there; ``Status`` is a plain word, so the two
channels don't compete.

Telegram HTML parse mode is used (not Markdown) because it has exactly one
escaping rule — ``& < >`` — which makes injection from an untrusted payload
tractable. Every value is escaped; only our own labels contain tags.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from .catalog import (
    BANNER_TEXT,
    BANNER_ALERT,
    PRIORITY_BADGE,
    EventSpec,
    platform_name,
)
from .redaction import REDACTED


# QUATA operates from Cameroon — West Africa Time, UTC+1, no DST. Every
# timestamp in a notification is WAT local time. The rendered value carries
# no suffix (the specified format is a bare `14:30`), so if QUATA ever
# operates across zones this constant is the one place to revisit.
DISPLAY_TZ = timezone(timedelta(hours=1), "WAT")

# Telegram hard-caps a message at 4096 characters.
MAX_MESSAGE_LENGTH = 4000


# Payload key → human label. Unlisted keys fall back to Title Case.
FIELD_LABELS: dict[str, str] = {
    # user
    "full_name": "Name",
    "username": "Username",
    "email": "Email",
    "phone": "Phone",
    "country": "Country",
    "user_id": "User ID",
    "registration_date": "Registration Date",
    "ip_address": "IP Address",
    "device_type": "Device Type",
    "role": "Role",
    "location": "Location",
    "attempts": "Failed Attempts",
    # money
    "amount": "Amount",
    "currency": "Currency",
    "fee": "Fees",
    "fees": "Fees",
    "payment_method": "Payment Method",
    "transaction_id": "Transaction Reference",
    "sender": "Sender",
    "receiver": "Receiver",
    "status": "Current Status",
    # food
    "restaurant": "Restaurant Name",
    "order_number": "Order Number",
    "customer": "Customer",
    "rider": "Rider",
    "delivery_address": "Delivery Address",
    # logistics
    "service_type": "Service Type",
    "pickup_location": "Pickup Location",
    "destination": "Destination",
    # trading
    "trade_id": "Trade ID",
    "buyer": "Buyer",
    "seller": "Seller",
    # infra
    "host": "Host",
    "service": "Service",
    "metric": "Metric",
    "value": "Value",
    "threshold": "Threshold",
    "error": "Error",
}

# Rendered by the envelope itself, never repeated in the field list.
_ENVELOPE_KEYS = {"reference", "occurred_at", "priority", "banner", "event", "platform"}


def escape(value: Any) -> str:
    """Escape the three characters Telegram HTML mode cares about."""
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def label_for(key: str) -> str:
    return FIELD_LABELS.get(key, str(key).replace("_", " ").strip().title())


def format_amount(value: Any) -> str:
    """Thousands-separate a numeric amount, leave anything else alone.

    Money in an alert has to be scannable — ``1,500,000`` reads as one and a
    half million at a glance; ``1500000`` does not.
    """
    if isinstance(value, bool) or value is None:
        return str(value)
    try:
        number = Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        return str(value)
    if number == number.to_integral_value():
        return f"{int(number):,}"
    return f"{number:,.2f}"


def format_timestamp(when: Optional[datetime] = None) -> tuple[str, str]:
    """Return ``("25 Jul 2026", "14:30")`` — the Date and Time block values."""
    moment = when or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    local = moment.astimezone(DISPLAY_TZ)
    return local.strftime("%d %b %Y"), local.strftime("%H:%M")


def _block(label: str, value: str) -> str:
    return f"<b>{escape(label)}:</b>\n{value}"


def _render_value(key: str, value: Any) -> Optional[str]:
    """Render one payload value, or None when it shouldn't be shown."""
    if value is None or value == "" or value == [] or value == {}:
        return None
    # A credential the publisher shouldn't have sent. The marker stays in
    # the stored payload so the bad integration is auditable, but printing
    # "Password: [redacted]" to a Telegram group only advertises that a
    # password was in flight. Drop it from the message.
    if value == REDACTED:
        return None
    if key in {"amount", "fee", "fees", "volume", "total"}:
        return escape(format_amount(value))
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (list, tuple)):
        return "\n".join(f"• {escape(v)}" for v in value)
    if isinstance(value, dict):
        return "\n".join(f"• {escape(label_for(k))}: {escape(v)}" for k, v in value.items())
    if isinstance(value, datetime):
        date_part, time_part = format_timestamp(value)
        return f"{date_part} {time_part}"
    return escape(value)


def render(
    *,
    spec: EventSpec,
    platform: str,
    payload: dict,
    priority: str,
    banner: Optional[str] = None,
    status: Optional[str] = None,
    reference: Optional[str] = None,
    occurred_at: Optional[datetime] = None,
) -> str:
    """Build the full Telegram message body for one event.

    ``payload`` must already be redacted — this function does not sanitise,
    it only escapes for the transport.
    """
    banner_key = banner or spec.banner or BANNER_ALERT
    parts: list[str] = [
        f"<b>{escape(BANNER_TEXT.get(banner_key, BANNER_TEXT[BANNER_ALERT]))}</b>",
        "",
        _block("Platform", escape(platform_name(platform))),
        "",
        _block("Priority", escape(PRIORITY_BADGE.get(priority, PRIORITY_BADGE["info"]))),
        "",
        _block("Event", escape(spec.label)),
        "",
        _block("Status", escape(status or spec.status)),
    ]

    # Catalogue-declared fields first, in their declared order, then
    # anything else the publisher sent. Keeps the important lines at a
    # predictable position across every event of the same type.
    seen: set[str] = set()
    ordered_keys: list[str] = []
    for key in spec.fields:
        if key in payload and key not in _ENVELOPE_KEYS:
            ordered_keys.append(key)
            seen.add(key)
    for key in payload:
        if key not in seen and key not in _ENVELOPE_KEYS:
            ordered_keys.append(key)

    for key in ordered_keys:
        rendered = _render_value(key, payload[key])
        if rendered is None:
            continue
        parts += ["", _block(label_for(key), rendered)]

    if reference:
        parts += ["", _block("Reference", escape(reference))]

    date_part, time_part = format_timestamp(occurred_at)
    parts += ["", _block("Date", escape(date_part)), "", _block("Time", escape(time_part))]

    message = "\n".join(parts)
    if len(message) > MAX_MESSAGE_LENGTH:
        # Cut on a line boundary so we never split an HTML tag in half —
        # Telegram rejects the whole message on malformed entities.
        message = message[:MAX_MESSAGE_LENGTH].rsplit("\n", 1)[0] + "\n\n<i>… truncated</i>"
    return message


def render_summary(*, title: str, sections: list[tuple[str, list[tuple[str, Any]]]],
                   occurred_at: Optional[datetime] = None) -> str:
    """Render the daily business summary.

    ``sections`` is ``[("QuataPay", [("New Users", 12), ("Deposits", 40)]), …]``
    — the digest builds it, this only lays it out.
    """
    parts = [f"<b>{escape(BANNER_TEXT['summary'])}</b>", "", f"<b>{escape(title)}</b>"]
    for section_title, rows in sections:
        parts += ["", f"<b>{escape(section_title)}</b>"]
        if not rows:
            parts.append("<i>No activity recorded</i>")
            continue
        for label, value in rows:
            shown = format_amount(value) if isinstance(value, (int, float, Decimal)) else str(value)
            parts.append(f"• {escape(label)}: <b>{escape(shown)}</b>")
    date_part, time_part = format_timestamp(occurred_at)
    parts += ["", _block("Date", escape(date_part)), "", _block("Time", escape(time_part))]

    message = "\n".join(parts)
    if len(message) > MAX_MESSAGE_LENGTH:
        message = message[:MAX_MESSAGE_LENGTH].rsplit("\n", 1)[0] + "\n\n<i>… truncated</i>"
    return message
