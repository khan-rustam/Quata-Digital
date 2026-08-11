"""The signature floor has to be enforced at boot, not merely defined.

``WHATSAPP_REQUIRE_SIGNATURE`` is the environment floor a database row cannot
lower (``settings_store.require_signature``). It gates the only
internet-facing door QCP has — ``POST /whatsapp/webhook/{account_slug}``.
With the floor off, that endpoint authenticates nothing: forged inbound
customer messages, forged conversations on the Verify number, forged status
callbacks marking real OTPs delivered.

Nothing checked it at startup, so one line in a server env file turned the
webhook back into an unauthenticated write API and the app booted happily.
A guard nobody can see is off is not a guard, so the combination
"delivery configured + floor off" is now a refusal to start.

Deliberately *not* scoped to ``ENVIRONMENT=production``: this fleet has
already been bitten by a production box whose ``is_production`` was false,
which failed every guard behind it open. Production is one trigger among
three, never the only one.

The dev escape hatch survives, but it is narrower than this file first
claimed. "It only needs ``WHATSAPP_ENABLED=false``" *was* the defect: that is
the delivery kill switch and inbound ingestion does not read it, so a dormant
box with credentials sat below the floor serving an unauthenticated write
API. Reaching the hatch now needs all three — the floor off, **no account
holding credentials**, and a non-production environment — and it warns on
every boot. The four tests below still pass unchanged; only this prose was
wrong. See ``tests/test_whatsapp_signature_floor_gap.py`` for the triggers.
"""
from __future__ import annotations

import importlib

import pytest

from app.core.config import ProductionConfigError, Settings


def _settings(**overrides) -> Settings:
    # `_env_file=None` skips the project .env so the test controls every value.
    return Settings(_env_file=None, **overrides)


def test_delivery_without_the_signature_floor_refuses_to_boot():
    s = _settings(WHATSAPP_ENABLED=True, WHATSAPP_REQUIRE_SIGNATURE=False)
    with pytest.raises(ProductionConfigError) as exc:
        s.assert_whatsapp_signature_floor()
    msg = str(exc.value)
    assert "WHATSAPP_REQUIRE_SIGNATURE" in msg
    assert "WHATSAPP_ENABLED" in msg


def test_delivery_with_the_floor_on_boots():
    _settings(
        WHATSAPP_ENABLED=True, WHATSAPP_REQUIRE_SIGNATURE=True
    ).assert_whatsapp_signature_floor()


def test_dormant_qcp_keeps_the_dev_escape_hatch():
    """QCP off is the default. Below the floor the admin toggle still decides,
    and a developer can still replay an unsigned webhook locally."""
    _settings(
        WHATSAPP_ENABLED=False, WHATSAPP_REQUIRE_SIGNATURE=False
    ).assert_whatsapp_signature_floor()


def test_the_guard_is_wired_into_boot(monkeypatch):
    """Defining the check is not enforcing it — importing the app must run it.

    Re-imports ``app.main`` with the unsafe combination in place and requires
    the import itself to fail, then restores the module for the rest of the
    session.
    """
    import app.main
    from app.core.config import settings as env_settings

    monkeypatch.setattr(env_settings, "WHATSAPP_ENABLED", True)
    monkeypatch.setattr(env_settings, "WHATSAPP_REQUIRE_SIGNATURE", False)
    try:
        with pytest.raises(ProductionConfigError):
            importlib.reload(app.main)
    finally:
        monkeypatch.undo()
        importlib.reload(app.main)
