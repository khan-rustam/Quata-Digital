"""
Pluggable email backend.

- console (default): prints the email to stdout. Perfect for dev.
- smtp: sends via configured SMTP server.
- disabled: silently no-ops.

Notification helpers wrap common events so callers don't think about formatting.
"""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import Iterable

from app.core.config import settings

log = logging.getLogger("quata.email")


def _recipients(to: str | Iterable[str]) -> list[str]:
    if isinstance(to, str):
        return [t.strip() for t in to.split(",") if t.strip()]
    return [t for t in to if t]


def send_email(*, to: str | Iterable[str], subject: str, body: str, html: str | None = None) -> bool:
    """Send an email via the configured backend. Returns True if dispatched."""
    recipients = _recipients(to)
    if not recipients:
        return False

    backend = settings.EMAIL_BACKEND.lower()

    if backend == "disabled":
        return False

    if backend == "console":
        rendered = (
            "\n" + "=" * 72
            + f"\n[email · console backend]"
            + f"\nTo: {', '.join(recipients)}"
            + f"\nFrom: {settings.EMAIL_FROM}"
            + f"\nSubject: {subject}"
            + "\n" + "-" * 72 + "\n"
            + body
            + "\n" + "=" * 72 + "\n"
        )
        log.info(rendered)
        print(rendered, flush=True)
        return True

    if backend == "smtp":
        msg = EmailMessage()
        msg["From"] = settings.EMAIL_FROM
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = subject
        msg.set_content(body)
        if html:
            msg.add_alternative(html, subtype="html")
        try:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
                if settings.SMTP_USE_TLS:
                    smtp.starttls()
                if settings.SMTP_USER:
                    smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                smtp.send_message(msg)
            return True
        except Exception as exc:  # noqa: BLE001
            log.exception("SMTP send failed: %s", exc)
            return False

    log.warning("Unknown EMAIL_BACKEND: %s", backend)
    return False


# ---- Notification helpers ----

def _ops_recipients() -> list[str]:
    if settings.EMAIL_NOTIFY_TO:
        return [r.strip() for r in settings.EMAIL_NOTIFY_TO.split(",") if r.strip()]
    return [settings.DEFAULT_ADMIN_EMAIL]


def notify_partner_received(partner_type: str, payload: dict) -> None:
    name = payload.get("company_name") or payload.get("full_name") or payload.get("name") or "Unknown"
    summary = "\n".join(f"  {k}: {v}" for k, v in payload.items())
    send_email(
        to=_ops_recipients(),
        subject=f"[QUATA] New {partner_type} partner request — {name}",
        body=f"A new partner request just landed.\n\n  Path: {partner_type}\n  Applicant: {name}\n\nDetails:\n{summary}\n",
    )


def notify_partner_status_changed(partner_id: int, partner_type: str, status: str, applicant_email: str | None) -> None:
    if applicant_email:
        send_email(
            to=applicant_email,
            subject=f"Your QUATA {partner_type} application — update",
            body=(
                f"Hi,\n\nThe status of your QUATA {partner_type} partner application "
                f"(#{partner_id}) is now: {status}.\n\nWe'll be in touch with next steps.\n\n"
                f"— The QUATA Partnerships team"
            ),
        )


def notify_application_received(job_title: str, applicant_email: str, applicant_name: str) -> None:
    send_email(
        to=applicant_email,
        subject=f"We got your application — {job_title}",
        body=(
            f"Hi {applicant_name},\n\nThanks for applying for {job_title} at QUATA Digital. "
            f"We've received your application and will review it shortly.\n\n"
            f"— The QUATA People team"
        ),
    )
    send_email(
        to=_ops_recipients(),
        subject=f"[QUATA] New applicant — {job_title}",
        body=f"A new applicant just submitted for {job_title}: {applicant_name} <{applicant_email}>",
    )


def notify_leave_decided(applicant_email: str, applicant_name: str, status: str, start: str, end: str) -> None:
    send_email(
        to=applicant_email,
        subject=f"Your leave request has been {status}",
        body=(
            f"Hi {applicant_name},\n\nYour leave request from {start} to {end} has been {status}.\n\n"
            f"— QUATA People"
        ),
    )


def notify_contact_received(payload: dict) -> None:
    summary = "\n".join(f"  {k}: {v}" for k, v in payload.items())
    send_email(
        to=_ops_recipients(),
        subject=f"[QUATA] Contact form — {payload.get('reason', 'general')}",
        body=f"New contact form submission:\n\n{summary}",
    )
