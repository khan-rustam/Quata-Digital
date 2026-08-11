"""Shared QCP test world: two numbers, one product, three templates.

Not a test module — a helper imported by ``test_whatsapp_invariant`` and
``test_whatsapp_idempotency`` so both exercise the same shape:

    Quata Verify  (authentication)  ──  login_otp        [authentication]
    QUATA         (engagement)      ──  order_dispatched [utility]
                                    ──  promo_weekend    [marketing]

Everything is created with a unique suffix so the module can run alongside
the rest of the suite in the shared session database. The one genuinely
global constraint is ``uq_whatsapp_accounts_active_purpose`` — at most one
*active* number per purpose — so setup deactivates whatever was active and
teardown deactivates its own, rather than deleting anyone's rows.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.models import (
    WhatsAppAccount,
    WhatsAppProduct,
    WhatsAppRoutingRule,
    WhatsAppTemplate,
)


@dataclass
class World:
    suffix: str
    verify: WhatsAppAccount
    quata: WhatsAppAccount
    product: WhatsAppProduct
    otp_template: WhatsAppTemplate
    order_template: WhatsAppTemplate
    promo_template: WhatsAppTemplate
    product_slug: str


def build(db: Session) -> World:
    from app.services.whatsapp.credentials import encrypt_wa_secret

    suffix = uuid.uuid4().hex[:8]
    # Credentials come from the database, never from code — so a world with
    # no token stored is a world that cannot send. Both numbers get an
    # obviously-fake one.
    token = encrypt_wa_secret(f"PYTEST_NOT_A_REAL_TOKEN_{suffix}")

    # Only one number per purpose may be active at a time — stand ours up
    # without destroying anyone else's rows.
    db.query(WhatsAppAccount).filter(WhatsAppAccount.is_active == True).update(  # noqa: E712
        {WhatsAppAccount.is_active: False}, synchronize_session=False
    )
    db.flush()

    verify = WhatsAppAccount(
        slug=f"quata_verify_{suffix}",
        name="Quata Verify",
        purpose="authentication",
        phone_number_id=f"PN_VERIFY_{suffix}",
        waba_id=f"WABA_VERIFY_{suffix}",
        display_phone="+237600000001",
        api_version="v21.0",
        access_token_encrypted=token,
        is_active=True,
        health="unknown",
    )
    quata = WhatsAppAccount(
        slug=f"quata_{suffix}",
        name="QUATA",
        purpose="engagement",
        phone_number_id=f"PN_QUATA_{suffix}",
        waba_id=f"WABA_QUATA_{suffix}",
        display_phone="+237600000002",
        api_version="v21.0",
        access_token_encrypted=token,
        is_active=True,
        health="unknown",
    )
    db.add_all([verify, quata])
    db.flush()

    product = WhatsAppProduct(
        slug=f"testpay_{suffix}",
        name="TestPay",
        is_enabled=True,
        api_key_hash="0" * 64,
        api_key_prefix="qcp_test_a1",
        allowed_purposes=["authentication", "engagement"],
        default_locale="en",
    )
    db.add(product)
    db.flush()

    otp_template = WhatsAppTemplate(
        account_id=verify.id,
        account_purpose="authentication",
        product_id=product.id,
        name=f"tp_login_otp_{suffix}",
        language="en",
        category="authentication",
        intent="login_otp",
        status="approved",
        variables=["code"],
    )
    order_template = WhatsAppTemplate(
        account_id=quata.id,
        account_purpose="engagement",
        product_id=product.id,
        name=f"tp_order_dispatched_{suffix}",
        language="en",
        category="utility",
        intent="order_dispatched",
        status="approved",
        variables=["order", "eta"],
    )
    promo_template = WhatsAppTemplate(
        account_id=quata.id,
        account_purpose="engagement",
        product_id=product.id,
        name=f"tp_promo_weekend_{suffix}",
        language="en",
        category="marketing",
        intent="promo_weekend",
        status="approved",
        variables=["offer"],
    )
    db.add_all([otp_template, order_template, promo_template])
    db.flush()

    rules = [
        # The correct pairings.
        ("login_otp", "authentication", "login_otp", "email"),
        ("order_dispatched", "engagement", "order_dispatched", "none"),
        ("promo_weekend", "engagement", "promo_weekend", "none"),
        # A rule that *tries* to put a marketing intent on the Verify number.
        ("promo_on_verify", "authentication", "promo_weekend", "none"),
        # A rule used to request a free-form text on the Verify number.
        ("otp_freeform", "authentication", "login_otp", "email"),
        # A free-form support reply on the engagement number.
        ("support_reply", "engagement", "support_reply", "none"),
    ]
    for intent, purpose, template_intent, fallback in rules:
        db.add(
            WhatsAppRoutingRule(
                product_id=product.id,
                intent=intent,
                purpose=purpose,
                template_intent=template_intent,
                locale=None,
                priority=100,
                is_active=True,
                fallback_channel=fallback,
                conditions={},
            )
        )
    db.commit()

    for obj in (verify, quata, product, otp_template, order_template, promo_template):
        db.refresh(obj)

    return World(
        suffix=suffix,
        verify=verify,
        quata=quata,
        product=product,
        otp_template=otp_template,
        order_template=order_template,
        promo_template=promo_template,
        product_slug=product.slug,
    )


def teardown(db: Session, world: World) -> None:
    """Stand our numbers down so the next module can raise its own."""
    db.query(WhatsAppAccount).filter(
        WhatsAppAccount.id.in_([world.verify.id, world.quata.id])
    ).update({WhatsAppAccount.is_active: False}, synchronize_session=False)
    db.commit()


def enable_delivery(monkeypatch, *, enabled: bool = True) -> None:
    """Flip both gates that ``settings_store.delivery_enabled`` reads.

    The env var is the kill switch; the site-settings key is the admin
    toggle. Both must say yes, which is the property under test.
    """
    from app.core.config import settings as env_settings
    from app.services import site_settings
    from app.services.whatsapp import settings_store

    monkeypatch.setattr(env_settings, "WHATSAPP_ENABLED", enabled)
    monkeypatch.setattr(
        site_settings,
        "get_setting",
        lambda key, default=None, **kw: (
            "true" if key == settings_store.KEY_DELIVERY_ENABLED and enabled else default
        ),
    )
    site_settings.invalidate_cache()
