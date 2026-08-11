"""The signature floor's coverage gap: the guard reads the wrong switch.

``assert_whatsapp_signature_floor`` fires on ``WHATSAPP_ENABLED=true`` AND
``WHATSAPP_REQUIRE_SIGNATURE=false``, and the documented dev escape hatch is
"just set ``WHATSAPP_ENABLED=false``".

But ``WHATSAPP_ENABLED`` is the *delivery* kill switch. Inbound webhook
ingestion does not read it: ``POST /whatsapp/webhook/{account_slug}`` is
served whether or not QCP may send, and its only authentication is
``settings_store.require_signature()``. So a box sitting dormant with the
floor turned off accepts forged inbound customer messages, forged
conversations on the Verify number and forged status callbacks — and boots
without a word.

Severity, stated honestly: ``WHATSAPP_REQUIRE_SIGNATURE`` defaults to
``True``, so a default install is safe and reaching this state takes a
deliberate edit to a server env file. What makes it worth closing is that the
edit is the one the documentation *recommends* reaching for, and nothing
tells the operator the door is now open.

Two additions, one refusal and one noise:

* the floor being off is a refusal to start whenever anything real is behind
  the door — an account holding credentials, or ``ENVIRONMENT=production``;
* below that, the hatch still works, but it announces itself at ``WARNING``
  on every boot instead of passing silently.

``ENVIRONMENT=production`` is an *additional* trigger here, never the only
one. A guard that fires only in production is the failure mode this fleet has
already shipped — a production box whose ``is_production`` was false failed
every guard behind it open.
"""
from __future__ import annotations

import logging

import pytest

from app.core.config import ProductionConfigError, Settings


def _settings(**overrides) -> Settings:
    # `_env_file=None` skips the project .env so the test controls every value.
    return Settings(_env_file=None, **overrides)


# ---------------------------------------------------------------------------
# The gap: dormant, so the old guard stayed quiet — but the door is open
# ---------------------------------------------------------------------------

def test_a_dormant_box_with_a_configured_account_refuses_to_boot():
    """Delivery off, credentials present, floor off — the reported gap."""
    s = _settings(
        WHATSAPP_ENABLED=False,
        WHATSAPP_REQUIRE_SIGNATURE=False,
        ENVIRONMENT="development",
    )
    with pytest.raises(ProductionConfigError) as exc:
        s.assert_whatsapp_signature_floor(accounts_configured=True)
    msg = str(exc.value)
    assert "WHATSAPP_REQUIRE_SIGNATURE" in msg
    # The refusal has to explain *why* dormancy did not save it, or the
    # operator's next move is to re-check WHATSAPP_ENABLED and conclude the
    # guard is broken.
    assert "webhook" in msg.lower()
    assert "WHATSAPP_ENABLED" in msg, "the message must say why 'turn delivery off' is not the fix"


def test_a_production_box_below_the_floor_refuses_to_boot():
    """Nothing legitimate runs the dev hatch in production."""
    s = _settings(
        WHATSAPP_ENABLED=False,
        WHATSAPP_REQUIRE_SIGNATURE=False,
        ENVIRONMENT="production",
    )
    with pytest.raises(ProductionConfigError) as exc:
        s.assert_whatsapp_signature_floor()
    assert "WHATSAPP_REQUIRE_SIGNATURE" in str(exc.value)


def test_production_is_an_extra_trigger_not_the_only_one():
    """The staging-drift failure mode must not be reintroduced.

    A box whose ENVIRONMENT has drifted to `development` is exactly where an
    unsigned webhook hides, so the account-backed refusal must fire there too.
    """
    s = _settings(
        WHATSAPP_ENABLED=False,
        WHATSAPP_REQUIRE_SIGNATURE=False,
        ENVIRONMENT="staging",
    )
    assert s.is_production is False
    with pytest.raises(ProductionConfigError):
        s.assert_whatsapp_signature_floor(accounts_configured=True)


# ---------------------------------------------------------------------------
# The hatch stays usable — and stops being silent
# ---------------------------------------------------------------------------

def test_the_dev_hatch_still_boots_with_nothing_behind_the_door(caplog):
    s = _settings(
        WHATSAPP_ENABLED=False,
        WHATSAPP_REQUIRE_SIGNATURE=False,
        ENVIRONMENT="development",
    )
    with caplog.at_level(logging.WARNING):
        s.assert_whatsapp_signature_floor(accounts_configured=False)


def test_the_dev_hatch_announces_itself_on_every_boot(caplog):
    """Silence was the actual defect — the box looked fine."""
    s = _settings(
        WHATSAPP_ENABLED=False,
        WHATSAPP_REQUIRE_SIGNATURE=False,
        ENVIRONMENT="development",
    )
    with caplog.at_level(logging.WARNING):
        s.assert_whatsapp_signature_floor()
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert warnings, "the dev hatch booted silently"
    assert any("WHATSAPP_REQUIRE_SIGNATURE" in r.getMessage() for r in warnings)


def test_the_floor_being_on_says_nothing_and_checks_nothing(caplog):
    """The normal case: no warning, no refusal, whatever else is configured."""
    s = _settings(WHATSAPP_ENABLED=True, WHATSAPP_REQUIRE_SIGNATURE=True)
    with caplog.at_level(logging.WARNING):
        s.assert_whatsapp_signature_floor(accounts_configured=True)
    assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []


# ---------------------------------------------------------------------------
# Nothing above weakens what was already refused
# ---------------------------------------------------------------------------

def test_delivery_below_the_floor_still_refuses_with_no_account_configured():
    s = _settings(WHATSAPP_ENABLED=True, WHATSAPP_REQUIRE_SIGNATURE=False)
    with pytest.raises(ProductionConfigError) as exc:
        s.assert_whatsapp_signature_floor(accounts_configured=False)
    msg = str(exc.value)
    assert "WHATSAPP_REQUIRE_SIGNATURE" in msg and "WHATSAPP_ENABLED" in msg


def test_the_guard_is_still_callable_with_no_arguments():
    """``app.main`` calls it bare; the new fact must be optional, not required."""
    _settings(
        WHATSAPP_ENABLED=True, WHATSAPP_REQUIRE_SIGNATURE=True
    ).assert_whatsapp_signature_floor()


# ---------------------------------------------------------------------------
# The fact the guard needs, resolved where a database query is allowed
# ---------------------------------------------------------------------------

def test_the_boot_probe_sees_an_account_holding_credentials():
    """Credentials, not activity, are what put a real number behind the door.

    Meta posts inbound messages and status callbacks whether or not the
    account is active and whether or not delivery is on, so the probe must
    not read either flag.
    """
    from app.db.session import SessionLocal, engine
    from app.models import Base, WhatsAppAccount
    from app.services.whatsapp import dispatch
    from app.services.whatsapp.credentials import encrypt_wa_secret

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    row = WhatsAppAccount(
        slug="probe_dormant_account",
        name="Probe",
        purpose="engagement",
        phone_number_id="PN_PROBE",
        waba_id="WABA_PROBE",
        display_phone="+237600009999",
        api_version="v21.0",
        access_token_encrypted=encrypt_wa_secret("PYTEST_NOT_A_REAL_TOKEN_PROBE"),
        is_active=False,  # dormant, exactly as QCP ships
        health="unknown",
    )
    try:
        db.add(row)
        db.commit()
        assert dispatch.accounts_configured() is True
    finally:
        db.delete(row)
        db.commit()
        db.close()


def test_the_boot_probe_never_stops_an_unmigrated_box_booting(monkeypatch):
    """A guard that refuses to start on a missing table is worse than the gap."""
    from app.services.whatsapp import dispatch

    def _explode():
        raise RuntimeError("no such table: whatsapp_accounts")

    monkeypatch.setattr(dispatch, "SessionLocal", _explode)
    assert dispatch.accounts_configured() is False
