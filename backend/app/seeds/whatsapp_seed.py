"""Bootstrap rows for QCP — the two WhatsApp accounts and the four known products.

**Everything seeded here is inert.** Both accounts land ``is_active=False``
with empty credentials, and every product lands ``is_enabled=False`` with no
API key. That is not caution for its own sake — it is the requirement:

* QuataFood owns the fleet's only WhatsApp authentication path (login OTP,
  payment-PIN reset OTP, phone-change verification), currently dormant behind
  its own master switch with all 28 templates still ``pending_approval`` at
  Meta.
* QuataPay's WhatsApp liveness is unknowable from its code — its credentials
  live in a production DB table, so it is one admin form submission away from
  live with no redeploy.

An account that arrived here already active could therefore start taking
traffic from a product that is still sending its own. So it doesn't arrive
active. Each product is migrated onto QCP by a human flipping
``whatsapp_products.is_enabled``, one at a time.

Additive only, exactly like ``services/notifications/recipients.py:41-45``:
a slug already present is left precisely as the administrator configured it,
so redeploying can never silently re-enable something that was deliberately
switched off, nor overwrite real credentials with these placeholders.

The other way a product reaches this table is ``POST /admin/qcp/products``,
which registers one disabled, keyless and engagement-only — the same shape
this seeder produces. (There is no plugin-file sync; the
``registry.sync_registry`` this docstring once named never existed.) This
seeder exists so the admin console has the four known products — and, more
importantly, the two accounts, which nothing else creates — on a fresh box.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models import WhatsAppAccount, WhatsAppProduct
from app.models.whatsapp import PURPOSE_AUTHENTICATION, PURPOSE_ENGAGEMENT


log = logging.getLogger("quata.whatsapp")


# The two numbers. The split is the entire point of QCP: Meta restricts a
# number that sends marketing traffic on an authentication template, so
# "Quata Verify" carries authentication and nothing else — enforced by the
# schema (see app/models/whatsapp.py), not by anyone remembering to.
ACCOUNTS: list[dict] = [
    {
        "slug": "quata_verify",
        "name": "Quata Verify",
        "purpose": PURPOSE_AUTHENTICATION,
        # OTP, login codes, password/PIN reset, device verification.
        # Templates of the ``authentication`` category and nothing else —
        # ``ck_whatsapp_templates_verify_is_auth_only``. Transaction and
        # security alerts are Meta ``utility`` and live on QUATA.
    },
    {
        "slug": "quata",
        "name": "QUATA",
        "purpose": PURPOSE_ENGAGEMENT,
        # Support, AI, campaigns, order and delivery updates, promotions.
    },
]


# The four products the fleet audit found. ``allowed_purposes`` is a ceiling,
# not a grant — it caps which account purposes a product may *ever* reach,
# and only matters once someone sets is_enabled=True.
PRODUCTS: list[dict] = [
    {
        "slug": "quatapay",
        "name": "QuataPay",
        "description": (
            "Wallet, merchant and payment platform. Sends zero authentication "
            "messages — email became its sole OTP channel on 2026-06-03 — so "
            "it is capped to the engagement account."
        ),
        # Engagement only, deliberately. Re-opening an auth path for QuataPay
        # must be a visible decision, not something this seed quietly allows.
        "allowed_purposes": [PURPOSE_ENGAGEMENT],
    },
    {
        "slug": "quatafood",
        "name": "QuataFood",
        "description": (
            "Food ordering and delivery. Owns the fleet's only WhatsApp "
            "authentication path (login OTP, payment-PIN reset OTP, "
            "phone-change verification) — the one product that legitimately "
            "needs the Quata Verify number."
        ),
        "allowed_purposes": [PURPOSE_AUTHENTICATION, PURPOSE_ENGAGEMENT],
    },
    {
        "slug": "abaqwa",
        "name": "Abaqwa",
        "description": (
            "Business infrastructure platform. WhatsApp integration is dormant "
            "today; engagement traffic only."
        ),
        "allowed_purposes": [PURPOSE_ENGAGEMENT],
    },
    {
        "slug": "quatatrade",
        "name": "QuataTrade",
        "description": (
            "Trading platform. Not a WhatsApp consumer at all today; "
            "registered so its migration is a switch rather than a build."
        ),
        "allowed_purposes": [PURPOSE_ENGAGEMENT],
    },
]


def seed_whatsapp_accounts(db: Session) -> int:
    """Create the two accounts, dormant and credential-free. Never updates."""
    created = 0
    for spec in ACCOUNTS:
        exists = (
            db.query(WhatsAppAccount)
            .filter(WhatsAppAccount.slug == spec["slug"])
            .first()
        )
        if exists:
            continue
        db.add(
            WhatsAppAccount(
                slug=spec["slug"],
                name=spec["name"],
                purpose=spec["purpose"],
                # Placeholders. An admin pastes the real Meta identifiers in;
                # with these empty the account cannot address the Graph API
                # even if something else went wrong.
                phone_number_id="",
                waba_id="",
                display_phone="",
                # No credentials. Not an empty string that could be mistaken
                # for a token — NULL.
                access_token_encrypted=None,
                app_secret_encrypted=None,
                webhook_verify_token_encrypted=None,
                api_version="v21.0",
                is_active=False,
                health="unknown",
            )
        )
        # Flush per row so the next existence check sees it, mirroring
        # recipients.seed_bootstrap_recipients.
        db.flush()
        created += 1
    if created:
        db.commit()
        log.info("whatsapp.accounts_seeded", extra={"count": created})
    return created


def seed_whatsapp_products(db: Session) -> int:
    """Create the four known products, disabled and keyless. Never updates."""
    created = 0
    for spec in PRODUCTS:
        exists = (
            db.query(WhatsAppProduct)
            .filter(WhatsAppProduct.slug == spec["slug"])
            .first()
        )
        if exists:
            continue
        db.add(
            WhatsAppProduct(
                slug=spec["slug"],
                name=spec["name"],
                description=spec["description"],
                # THE migration gate.
                is_enabled=False,
                # No key issued. No sha256 hex digest equals "", so this
                # product cannot authenticate until an admin rotates a key in.
                api_key_hash="",
                api_key_prefix="",
                allowed_purposes=spec["allowed_purposes"],
                default_locale="en",
                rate_limit_per_minute=600,
            )
        )
        db.flush()
        created += 1
    if created:
        db.commit()
        log.info("whatsapp.products_seeded", extra={"count": created})
    return created


def seed_whatsapp(db: Session) -> dict:
    """Both seeders. Safe to call on every boot."""
    return {
        "accounts": seed_whatsapp_accounts(db),
        "products": seed_whatsapp_products(db),
    }
