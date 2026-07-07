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
import ssl
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
        # `log.info(rendered)` already lands in stdout for the console
        # backend; the extra `print` duplicated reset-tokens into a less
        # structured stream.
        log.info(rendered)
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
            # Port 465 is implicit TLS (SMTPS) — connect with SMTP_SSL. Ports
            # 587/25 start plaintext and upgrade via STARTTLS. Using the wrong
            # transport for the port hangs or fails the handshake, so pick by
            # port rather than assuming one style.
            if settings.SMTP_PORT == 465:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(
                    settings.SMTP_HOST, settings.SMTP_PORT, timeout=20, context=context
                ) as smtp:
                    if settings.SMTP_USER:
                        smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                    smtp.send_message(msg)
            else:
                with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as smtp:
                    if settings.SMTP_USE_TLS:
                        smtp.starttls(context=ssl.create_default_context())
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


def notify_application_received(
    job_title: str,
    applicant_email: str,
    applicant_name: str,
    application_id: int | None = None,
    applicant_phone: str | None = None,
) -> None:
    send_email(
        to=applicant_email,
        subject=f"We got your application — {job_title}",
        body=(
            f"Hi {applicant_name},\n\nThanks for applying for {job_title} at QUATA Digital. "
            f"We've received your application and will review it shortly.\n\n"
            f"— The QUATA People team"
        ),
    )
    # Ops notification with a direct link into the admin. The CV is private
    # (not a public URL), so we link to the review screen — the reviewer signs
    # in and uses View / Download CV there — rather than exposing the file.
    base = (settings.FRONTEND_URL or "").rstrip("/")
    review_link = (
        f"{base}/admin/careers?applicant={application_id}"
        if application_id
        else f"{base}/admin/careers"
    )
    lines = [
        f"A new applicant just submitted for {job_title}:",
        "",
        f"  Name:  {applicant_name}",
        f"  Email: {applicant_email}",
    ]
    if applicant_phone:
        lines.append(f"  Phone: {applicant_phone}")
    lines += [
        "",
        "Review the application and open the CV (view or download) here:",
        review_link,
        "",
        "You'll need to sign in — CVs are private and only visible to staff.",
    ]
    send_email(
        to=_ops_recipients(),
        subject=f"[QUATA] New applicant — {job_title}",
        body="\n".join(lines),
    )


def _careers_recipients() -> list[str]:
    """Mailbox(es) that get a copy of every hiring-workflow email."""
    raw = settings.CAREERS_NOTIFY_TO or ""
    return [r.strip() for r in raw.split(",") if r.strip()]


def notify_applicant_shortlisted(
    *,
    applicant_email: str,
    applicant_name: str,
    job_title: str,
    interview_when: str | None,
    interview_location: str | None,
    documents: str | None,
    message: str | None = None,
) -> None:
    """Tell a shortlisted candidate they've advanced, with interview details.

    Sends to the candidate and copies the careers mailbox. Best-effort: a
    mail failure must not roll back the status change (caller wraps this).
    """
    lines = [
        f"Hi {applicant_name},",
        "",
        f"Good news — you've been shortlisted for the {job_title} role at "
        f"QUATA Digital and we'd like to invite you to an interview.",
    ]
    if interview_when:
        lines += ["", f"Interview date & time: {interview_when}"]
    if interview_location:
        lines.append(f"Location: {interview_location}")
    if documents:
        lines += ["", "Please bring the following documents with you:", documents]
    if message:
        lines += ["", message]
    lines += ["", "We look forward to meeting you.", "", "— The QUATA People team"]
    send_email(
        to=applicant_email,
        subject=f"You've been shortlisted — {job_title} at QUATA Digital",
        body="\n".join(lines),
    )
    careers = _careers_recipients()
    if careers:
        send_email(
            to=careers,
            subject=f"[QUATA Careers] Shortlisted — {applicant_name} ({job_title})",
            body=(
                f"{applicant_name} <{applicant_email}> was shortlisted for {job_title}.\n"
                f"Interview: {interview_when or '—'} · {interview_location or '—'}"
            ),
        )


def notify_applicant_hired(
    *,
    applicant_email: str,
    applicant_name: str,
    job_title: str,
    start_when: str | None,
    message: str | None = None,
) -> None:
    """Congratulate a hired candidate and give them their start date."""
    lines = [
        f"Hi {applicant_name},",
        "",
        f"Congratulations! We're delighted to offer you the {job_title} role "
        f"at QUATA Digital — welcome to the team.",
    ]
    if start_when:
        lines += ["", f"Your start date is: {start_when}"]
    if message:
        lines += ["", message]
    lines += [
        "",
        "We'll follow up shortly with onboarding details.",
        "",
        "— The QUATA People team",
    ]
    send_email(
        to=applicant_email,
        subject=f"Offer — {job_title} at QUATA Digital",
        body="\n".join(lines),
    )
    careers = _careers_recipients()
    if careers:
        send_email(
            to=careers,
            subject=f"[QUATA Careers] Hired — {applicant_name} ({job_title})",
            body=(
                f"{applicant_name} <{applicant_email}> was hired for {job_title}.\n"
                f"Start date: {start_when or '—'}"
            ),
        )


def notify_applicant_rejected(
    *,
    applicant_email: str,
    applicant_name: str,
    job_title: str,
    message: str | None = None,
) -> None:
    """Send a courteous 'not moving forward' note to the candidate."""
    body = message or (
        f"Hi {applicant_name},\n\n"
        f"Thank you for your interest in the {job_title} role at QUATA Digital "
        f"and for the time you invested in your application. After careful "
        f"consideration we won't be moving forward on this occasion.\n\n"
        f"We were impressed by many candidates and encourage you to apply for "
        f"future roles that match your skills. We wish you the very best.\n\n"
        f"— The QUATA People team"
    )
    send_email(
        to=applicant_email,
        subject=f"Update on your application — {job_title} at QUATA Digital",
        body=body,
    )
    careers = _careers_recipients()
    if careers:
        send_email(
            to=careers,
            subject=f"[QUATA Careers] Rejected — {applicant_name} ({job_title})",
            body=f"{applicant_name} <{applicant_email}> was rejected for {job_title}.",
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
