"""Provider text is written by Meta, so it may not be trusted with our secrets.

A credential reaches the database through an *error string*. Meta echoes the
token you sent it back at you — whole, truncated, URL-escaped, JSON-escaped,
wrapped in a ``Bearer`` header, or hanging off a signed media URL — and QCP
then writes that string down: ``whatsapp_messages.last_error``,
``whatsapp_accounts.last_error``, the audit row's ``reason``, and the dict the
admin console renders.

The original defence was ``text.replace(token, "***")``: an exact match on the
one token the caller happened to be holding. That catches exactly one of the
shapes below and none of the others — not a fragment, not an escaped copy, not
the app secret, not a *different* account's token, not a proof hash.

So the rule these tests pin is shape, not equality: anything that *looks* like
a credential is stripped before it is persisted, whether or not we hold a copy
to compare it against.

The second half of the file is as load-bearing as the first. A scrub that
reduces every failure to ``"***"`` makes ``last_error`` worthless, and the
next person to debug a delivery failure will delete it. Meta's ordinary error
text must survive intact.
"""
from __future__ import annotations

import urllib.parse

import pytest

from app.db.session import SessionLocal, engine
from app.models import Base, WhatsAppAccount, WhatsAppAuditLog, WhatsAppMessage
from app.services.whatsapp import dispatch, meta

from . import whatsapp_world


# ---------------------------------------------------------------------------
# The shapes
# ---------------------------------------------------------------------------
# Obviously synthetic, but structurally what Meta hands back. The ``/`` in the
# access token is deliberate: it is what makes the JSON-escaped copy differ
# byte-for-byte from the value we hold.

ACCESS_TOKEN = "EAAG" + "8ZBv1k/QZCdp7m3X" * 9
OTHER_TOKEN = "EAAB" + "3xQZDpLm7wR4tY6u" * 9
APP_SECRET = "9f3c1d7b0a4e6528d1c9b7a35f204e68"          # 32 hex
APPSECRET_PROOF = "c4e2" * 16                             # 64 hex
OPAQUE_SESSION = "7Kq2Vb9NfR4tZ1sXmA6uPd3EwYc8HjLg"       # 32 chars, no prefix

URL_ESCAPED = urllib.parse.quote(ACCESS_TOKEN, safe="")
JSON_ESCAPED = ACCESS_TOKEN.replace("/", "\\/")
TRUNCATED = ACCESS_TOKEN[:28]

# Every disclosure shape the persisted string must not contain.
LEAKED = (
    ("the whole access token", ACCESS_TOKEN),
    ("a truncated access token", TRUNCATED),
    ("a URL-escaped access token", URL_ESCAPED),
    ("a JSON-escaped access token", JSON_ESCAPED),
    ("a different account's token", OTHER_TOKEN),
    ("the app secret", APP_SECRET),
    ("an appsecret_proof", APPSECRET_PROOF),
    ("an opaque high-entropy session key", OPAQUE_SESSION),
)

# What a *useful* error still has to say once the credentials are gone.
USEFUL = (
    "(#190)",
    "Error validating access token",
    "has expired",
    "lookaside.fbsbx.com",
    "fbtrace_id",
)

LEAKY_META_ERROR = (
    "(#190) Error validating access token: the session has expired. "
    f"Authorization: Bearer {ACCESS_TOKEN} was revoked; "
    f"retry with token={TRUNCATED} or refresh via "
    f"https://lookaside.fbsbx.com/whatsapp_business/attachments/"
    f"?mid=1042&access_token={URL_ESCAPED}&appsecret_proof={APPSECRET_PROOF} "
    f'debug={{"app_secret":"{APP_SECRET}",'
    f'"peer_token":"{OTHER_TOKEN}",'
    f'"escaped":"{JSON_ESCAPED}",'
    f'"session_key":"{OPAQUE_SESSION}"}} '
    "fbtrace_id Ax7Bq2Cd9Ef"
)

# The floor below which a run of a credential is not a disclosure. Twelve
# characters of a Meta token is far more than "just the first few".
_FRAGMENT_FLOOR = 12


def assert_no_fragment(text: str, secret: str, label: str) -> None:
    """No 12-character window of *secret* may survive anywhere in *text*."""
    haystack = text or ""
    for start in range(0, len(secret) - _FRAGMENT_FLOOR + 1):
        window = secret[start : start + _FRAGMENT_FLOOR]
        assert window not in haystack, (
            f"{label}: a {_FRAGMENT_FLOOR}-character run at offset {start} survived"
        )


def assert_clean_and_useful(text: str, where: str) -> None:
    for label, secret in LEAKED:
        assert_no_fragment(text, secret, f"{where} / {label}")
    for phrase in USEFUL:
        assert phrase in (text or ""), f"{where}: scrubbing destroyed {phrase!r}"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def world():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        built = whatsapp_world.build(db)
        yield built
        whatsapp_world.teardown(db, built)
    finally:
        db.close()


@pytest.fixture
def live(monkeypatch):
    whatsapp_world.enable_delivery(monkeypatch, enabled=True)


# ---------------------------------------------------------------------------
# The scrubber itself
# ---------------------------------------------------------------------------

def test_every_credential_shape_is_stripped_without_holding_a_copy():
    """Not one of these values is passed in. Shape is the only signal."""
    cleaned = meta.scrub_provider_text(LEAKY_META_ERROR)
    assert_clean_and_useful(cleaned, "scrub_provider_text")


def test_the_exact_match_replacement_is_kept_as_well():
    """Belt and braces: a held credential is removed even without a shape.

    The world's own stored token is deliberately shapeless — no ``EAA``
    prefix, no digits, too short for the entropy rule — so only the
    exact/prefix path can remove it.
    """
    held = "PYTEST_HELD_CREDENTIAL_WITH_NO_SHAPE"
    cleaned = meta.scrub_provider_text(f"(#190) rejected {held} at the edge", held)
    assert held not in cleaned
    assert_no_fragment(cleaned, held, "held credential")
    assert "(#190)" in cleaned and "at the edge" in cleaned


@pytest.mark.parametrize(
    "ordinary",
    [
        "(#131047) Re-engagement message: Message failed to send because more "
        "than 24 hours have passed since the customer last replied to this number.",
        "(#132000) Number of parameters does not match the expected number of params",
        "(#132001) Template name does not exist in the translation",
        "(#131026) Message undeliverable: receiver is incapable of receiving this message",
        "Recipient phone number not in allowed list: +237600000009",
        "URLError: <urlopen error [Errno 60] Operation timed out>",
    ],
)
def test_an_ordinary_meta_error_survives_untouched(ordinary):
    """The half of the contract that stops someone deleting the column."""
    assert meta.scrub_provider_text(ordinary) == ordinary


def test_identifiers_the_console_needs_are_not_credentials():
    """Phone number ids, WABA ids and message ids stay readable."""
    text = (
        "(#100) Object with ID '105432198765432' does not exist on WABA "
        "104928374651029 for message wamid.HBgLMjM3NjAwMDAwMDk"
    )
    cleaned = meta.scrub_provider_text(text)
    assert "105432198765432" in cleaned
    assert "104928374651029" in cleaned


# ---------------------------------------------------------------------------
# Sink 1 — whatsapp_messages.last_error (the send-failure path)
# ---------------------------------------------------------------------------

def test_the_send_failure_path_does_not_persist_a_credential(world, live, monkeypatch):
    """The sink reported in an earlier round and left: ``row.last_error``."""
    def _leaky_call(url, *, token, payload=None, method="POST"):
        return (
            False,
            {"error": {"code": 190, "message": LEAKY_META_ERROR}},
            LEAKY_META_ERROR,
            401,
        )

    monkeypatch.setattr(meta, "_call", _leaky_call)

    accepted = dispatch.send(
        product_slug=world.product_slug,
        intent="order_dispatched",
        to_phone_e164="+237600000031",
        variables=("ORD-77", "18:40"),
        dispatch=False,
    )
    assert accepted["status"] == dispatch.STATUS_QUEUED, accepted

    outcome = dispatch.deliver_message(
        accepted["message_uid"], {"variables": ["ORD-77", "18:40"], "body": None}
    )
    assert outcome["ok"] is False

    with SessionLocal() as db:
        row = (
            db.query(WhatsAppMessage)
            .filter(WhatsAppMessage.message_uid == accepted["message_uid"])
            .one()
        )
        stored = row.last_error or ""
        assert stored, "the failure must still say why"
        assert_clean_and_useful(stored, "whatsapp_messages.last_error")
        assert row.error_code == "190"

    # …and the dict handed back to the caller carries the same scrubbed text.
    for label, secret in LEAKED:
        assert_no_fragment(str(outcome.get("error") or ""), secret, f"returned dict / {label}")


def test_the_send_failure_audit_row_does_not_carry_a_credential(world, live, monkeypatch):
    """A dead-lettered message writes an audit row. It is a sink too."""
    def _leaky_call(url, *, token, payload=None, method="POST"):
        return (False, {"error": {"code": 190, "message": LEAKY_META_ERROR}}, LEAKY_META_ERROR, 401)

    monkeypatch.setattr(meta, "_call", _leaky_call)

    accepted = dispatch.send(
        product_slug=world.product_slug,
        intent="order_dispatched",
        to_phone_e164="+237600000032",
        variables=("ORD-78", "19:10"),
        dispatch=False,
    )
    dispatch.deliver_message(
        accepted["message_uid"], {"variables": ["ORD-78", "19:10"], "body": None}
    )

    with SessionLocal() as db:
        rows = (
            db.query(WhatsAppAuditLog)
            .filter(WhatsAppAuditLog.resource_id == accepted["message_uid"])
            .all()
        )
        blob = " ".join(f"{r.reason or ''} {r.details or {}}" for r in rows)
    for label, secret in LEAKED:
        assert_no_fragment(blob, secret, f"whatsapp_audit_log / {label}")


def test_a_held_token_echoed_by_meta_is_still_removed(world, live, monkeypatch):
    """The account's own credential, exact-matched, end to end."""
    from app.services.whatsapp import credentials

    held = "PYTEST_ECHOED_ACCOUNT_CREDENTIAL_VALUE"
    with SessionLocal() as db:
        account = db.query(WhatsAppAccount).filter(WhatsAppAccount.id == world.quata.id).one()
        original = account.access_token_encrypted
        account.access_token_encrypted = credentials.encrypt_wa_secret(held)
        db.commit()

    try:
        def _leaky_call(url, *, token, payload=None, method="POST"):
            return (
                False,
                {"error": {"code": 131000, "message": f"(#131000) rejected {held} upstream"}},
                f"(#131000) rejected {held} upstream",
                500,
            )

        monkeypatch.setattr(meta, "_call", _leaky_call)
        accepted = dispatch.send(
            product_slug=world.product_slug,
            intent="order_dispatched",
            to_phone_e164="+237600000033",
            variables=("ORD-79", "20:00"),
            dispatch=False,
        )
        dispatch.deliver_message(
            accepted["message_uid"], {"variables": ["ORD-79", "20:00"], "body": None}
        )
        with SessionLocal() as db:
            row = (
                db.query(WhatsAppMessage)
                .filter(WhatsAppMessage.message_uid == accepted["message_uid"])
                .one()
            )
            assert_no_fragment(row.last_error or "", held, "held token / row.last_error")
            assert "(#131000)" in (row.last_error or "")
    finally:
        with SessionLocal() as db:
            account = db.query(WhatsAppAccount).filter(WhatsAppAccount.id == world.quata.id).one()
            account.access_token_encrypted = original
            db.commit()


# ---------------------------------------------------------------------------
# Sink 2 — whatsapp_accounts.last_error
# ---------------------------------------------------------------------------

def test_the_account_health_sink_does_not_persist_a_credential(world, monkeypatch):
    monkeypatch.setattr(
        meta,
        "get_phone_health",
        lambda account, *, db: {"ok": False, "error": LEAKY_META_ERROR, "unauthorized": True},
    )
    with SessionLocal() as db:
        account = db.query(WhatsAppAccount).filter(WhatsAppAccount.id == world.quata.id).one()
        result = dispatch.fetch_phone_health(db, account)
        stored = account.last_error or ""
        audit_blob = " ".join(
            r.reason or ""
            for r in db.query(WhatsAppAuditLog)
            .filter(
                WhatsAppAuditLog.account_id == world.quata.id,
                WhatsAppAuditLog.action == "account.health_checked",
            )
            .all()
        )

    assert stored, "a degraded account must still say why"
    assert_clean_and_useful(stored, "whatsapp_accounts.last_error")
    for label, secret in LEAKED:
        assert_no_fragment(str(result.get("error") or ""), secret, f"returned dict / {label}")
        assert_no_fragment(audit_blob, secret, f"audit reason / {label}")


# ---------------------------------------------------------------------------
# Sink 3 — the template sync result and its audit row
# ---------------------------------------------------------------------------

def test_the_template_sync_sink_does_not_leak_a_credential(world, monkeypatch):
    monkeypatch.setattr(
        meta,
        "list_message_templates",
        lambda account, *, db: {"ok": False, "error": LEAKY_META_ERROR, "data": []},
    )
    with SessionLocal() as db:
        account = db.query(WhatsAppAccount).filter(WhatsAppAccount.id == world.quata.id).one()
        result = dispatch.fetch_message_templates(db, account)
        db.commit()
        audit_blob = " ".join(
            r.reason or ""
            for r in db.query(WhatsAppAuditLog)
            .filter(
                WhatsAppAuditLog.account_id == world.quata.id,
                WhatsAppAuditLog.action == "template.synced",
            )
            .all()
        )

    assert_clean_and_useful(str(result.get("error") or ""), "template sync result")
    for label, secret in LEAKED:
        assert_no_fragment(audit_blob, secret, f"template.synced audit / {label}")


# ---------------------------------------------------------------------------
# Sink 4 — the transport's own return value
# ---------------------------------------------------------------------------

def test_the_transport_result_is_scrubbed_before_it_leaves_meta_py(world, live, monkeypatch):
    """``meta`` must not hand dispatch a string it would be unsafe to store."""
    from app.services.whatsapp import routing

    def _leaky_call(url, *, token, payload=None, method="POST"):
        return (False, {"error": {"code": 190, "message": LEAKY_META_ERROR}}, LEAKY_META_ERROR, 401)

    monkeypatch.setattr(meta, "_call", _leaky_call)
    with SessionLocal() as db:
        ticket = routing.resolve_route(
            db,
            product_slug=world.product_slug,
            intent="order_dispatched",
            to_phone_e164="+237600000034",
            kind="template",
            locale=None,
            variables=("ORD-80", "21:00"),
        )
        result = meta.send_template(ticket, db=db)
        db.rollback()

    assert result.ok is False
    for label, secret in LEAKED:
        assert_no_fragment(result.error or "", secret, f"SendResult.error / {label}")
    assert "(#190)" in (result.error or "")
