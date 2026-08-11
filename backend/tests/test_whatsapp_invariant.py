"""The account-purpose invariant. These are the load-bearing tests in QCP.

Two Meta numbers, and the separation between them is the whole product:

* **Quata Verify** sends approved *authentication* templates and nothing
  else — no marketing, no free-form.
* **QUATA** sends everything else.

Meta restricts numbers that send marketing on an authentication template, so
a violation must be *impossible*, not discouraged. Four layers enforce it and
each is tested here:

* **L1 — the database.** A template row that pairs ``marketing`` with the
  Verify number cannot be inserted, and a message row cannot pair one
  account's number with the other account's template.
* **L2 — ``resolve_route()``.** The single choke point; every send crosses
  it, and the first failed check raises ``RoutingDenied`` with a stable code.
* **L3 — ``meta.py``.** Re-verifies the ticket HMAC and re-asserts the
  category rules from the ticket's own fields before any socket is opened.
* **L4 — the import boundary.** Covered by ``test_whatsapp_boundaries.py``.

If any test in this file ever fails, QCP can send marketing from the number
QuataFood's login OTP depends on, and Meta can restrict it.
"""
from __future__ import annotations

import dataclasses
import io
import json
import urllib.error

import pytest
from sqlalchemy import create_engine, text as sql_text
from sqlalchemy.exc import IntegrityError

from app.db.session import SessionLocal, engine
from app.models import (
    Base,
    WhatsAppAccount,
    WhatsAppAuditLog,
    WhatsAppMessage,
    WhatsAppTemplate,
)
from app.services.whatsapp import meta, routing
from app.services.whatsapp.routing import RoutingDenied

from . import whatsapp_world


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
    """Both dormancy gates open, so routing reaches its purpose checks."""
    whatsapp_world.enable_delivery(monkeypatch, enabled=True)


@pytest.fixture
def no_http(monkeypatch):
    """Record every provider call. Any entry means HTTP would have been issued."""
    calls: list[dict] = []

    def _recorder(url, *, token, payload=None, method="POST"):
        calls.append({"url": url, "payload": payload, "method": method})
        return True, {"messages": [{"id": "wamid.TEST"}]}, None, 200

    monkeypatch.setattr(meta, "_call", _recorder)
    return calls


# ---------------------------------------------------------------------------
# L1 — a violating row cannot exist
# ---------------------------------------------------------------------------

def test_marketing_template_cannot_live_on_the_verify_number(world):
    """The single most important constraint in the schema."""
    db = SessionLocal()
    try:
        db.add(
            WhatsAppTemplate(
                account_id=world.verify.id,
                account_purpose="authentication",
                name=f"tp_illegal_marketing_{world.suffix}",
                language="en",
                category="marketing",
                intent="promo_illegal",
                status="approved",
                variables=["offer"],
            )
        )
        with pytest.raises(IntegrityError):
            db.flush()
    finally:
        db.rollback()
        db.close()


def test_authentication_template_cannot_live_on_the_engagement_number(world):
    db = SessionLocal()
    try:
        db.add(
            WhatsAppTemplate(
                account_id=world.quata.id,
                account_purpose="engagement",
                name=f"tp_illegal_auth_{world.suffix}",
                language="en",
                category="authentication",
                intent="otp_illegal",
                status="approved",
                variables=["code"],
            )
        )
        with pytest.raises(IntegrityError):
            db.flush()
    finally:
        db.rollback()
        db.close()


def test_utility_template_cannot_live_on_the_verify_number(world):
    """Quata Verify accepts the ``authentication`` category and nothing else.

    ``category`` is operator-typed data — no code path in QCP creates a
    template, and nothing syncs Meta's classification back. So a template
    filed as ``utility`` is only utility until Meta says otherwise, and Meta
    re-classifies. Transaction and security alerts belong on QUATA, where a
    re-classification cannot restrict the number QuataFood's login OTP needs.
    """
    db = SessionLocal()
    try:
        db.add(
            WhatsAppTemplate(
                account_id=world.verify.id,
                account_purpose="authentication",
                name=f"tp_illegal_utility_{world.suffix}",
                language="en",
                category="utility",
                intent="security_alert_illegal",
                status="approved",
                variables=["amount"],
            )
        )
        with pytest.raises(IntegrityError):
            db.flush()
    finally:
        db.rollback()
        db.close()


_INSERT_MESSAGE = sql_text(
    """
    INSERT INTO whatsapp_messages
        (message_uid, account_id, account_purpose, template_id,
         direction, kind, status, attempts, max_attempts)
    VALUES
        (:uid, :account_id, :purpose, :template_id,
         'outbound', 'template', 'queued', 0, 5)
    """
)


def test_message_cannot_pair_the_verify_number_with_an_engagement_template(world):
    """The composite FK ``fk_whatsapp_messages_template_purpose``.

    Run against a connection with referential integrity switched on, because
    that is what production (Postgres) always has. The row names the Verify
    account and a template bound to the engagement account: there is no
    ``(template_id, 'authentication')`` pair for it to point at.
    """
    with engine.connect() as conn:
        try:
            if engine.dialect.name == "sqlite":
                conn.exec_driver_sql("PRAGMA foreign_keys=ON")

            # Control: the legal pairing inserts cleanly on this same
            # connection, so the failure below is the FK and not something
            # incidental.
            conn.execute(
                _INSERT_MESSAGE,
                {
                    "uid": f"ctl{world.suffix}",
                    "account_id": world.verify.id,
                    "purpose": "authentication",
                    "template_id": world.otp_template.id,
                },
            )

            with pytest.raises(IntegrityError):
                conn.execute(
                    _INSERT_MESSAGE,
                    {
                        "uid": f"bad{world.suffix}",
                        "account_id": world.verify.id,
                        "purpose": "authentication",
                        "template_id": world.promo_template.id,
                    },
                )
        finally:
            conn.rollback()
            if engine.dialect.name == "sqlite":
                # The pragma is per-connection and this one goes back to the
                # pool. Leaving it on would silently change behaviour for
                # whatever borrows it next.
                conn.exec_driver_sql("PRAGMA foreign_keys=OFF")


def test_sqlite_dev_does_not_enforce_the_foreign_key_layer(world):
    """Documents the dialect gap the module docstring warns about.

    In dev, ``PRAGMA foreign_keys`` is off, so L1's FK half is inert and the
    CHECK constraints plus ``resolve_route`` carry the invariant. This test
    exists so that gap is a stated, visible fact rather than a surprise.
    """
    if engine.dialect.name != "sqlite":
        pytest.skip("Postgres enforces foreign keys unconditionally")
    # A fresh engine, so the answer is the repo's default rather than
    # whatever a pooled connection was last used for.
    probe = create_engine(str(engine.url))
    try:
        with probe.connect() as conn:
            enforced = conn.exec_driver_sql("PRAGMA foreign_keys").scalar()
    finally:
        probe.dispose()
    assert enforced == 0


# ---------------------------------------------------------------------------
# L2 — resolve_route: the correct pairings pass
# ---------------------------------------------------------------------------

def test_auth_template_on_verify_resolves(world, live):
    db = SessionLocal()
    try:
        ticket = routing.resolve_route(
            db,
            product_slug=world.product_slug,
            intent="login_otp",
            to_phone_e164="+237600000009",
            variables=("482913",),
        )
    finally:
        db.close()
    assert ticket.account_id == world.verify.id
    assert ticket.account_purpose == "authentication"
    assert ticket.template_category == "authentication"
    assert ticket.template_id == world.otp_template.id
    assert ticket.phone_number_id == world.verify.phone_number_id
    assert ticket.checksum == routing.ticket_checksum(ticket)


def test_utility_template_on_the_engagement_number_resolves(world, live):
    db = SessionLocal()
    try:
        ticket = routing.resolve_route(
            db,
            product_slug=world.product_slug,
            intent="order_dispatched",
            to_phone_e164="+237600000009",
            variables=("ORD-1", "18:40"),
        )
    finally:
        db.close()
    assert ticket.account_id == world.quata.id
    assert ticket.account_purpose == "engagement"
    assert ticket.template_category == "utility"


def test_marketing_template_on_the_engagement_number_resolves(world, live):
    """Marketing is legal — on the QUATA number, and only there."""
    db = SessionLocal()
    try:
        ticket = routing.resolve_route(
            db,
            product_slug=world.product_slug,
            intent="promo_weekend",
            to_phone_e164="+237600000009",
            variables=("2 for 1",),
        )
    finally:
        db.close()
    assert ticket.account_purpose == "engagement"
    assert ticket.template_category == "marketing"


# ---------------------------------------------------------------------------
# L2 — resolve_route: the violations are refused
# ---------------------------------------------------------------------------

def test_marketing_intent_routed_to_the_verify_number_is_refused(world, live):
    """A rule that points a marketing intent at ``purpose='authentication'``.

    It cannot resolve, and the reason is itself the invariant: the marketing
    template it names is physically unable to exist on the Verify account
    (``ck_whatsapp_templates_marketing_never_on_verify``), so the lookup on
    that account finds nothing. Either way no ticket is minted.
    """
    db = SessionLocal()
    try:
        with pytest.raises(RoutingDenied) as excinfo:
            routing.resolve_route(
                db,
                product_slug=world.product_slug,
                intent="promo_on_verify",
                to_phone_e164="+237600000009",
                variables=("2 for 1",),
            )
    finally:
        db.rollback()
        db.close()
    assert excinfo.value.reason in {"template_not_approved", "marketing_on_auth_account"}


def test_freeform_on_the_verify_number_is_refused(world, live):
    """The Verify number can only ever emit approved templates."""
    db = SessionLocal()
    try:
        with pytest.raises(RoutingDenied) as excinfo:
            routing.resolve_route(
                db,
                product_slug=world.product_slug,
                intent="otp_freeform",
                to_phone_e164="+237600000009",
                kind="text",
            )
    finally:
        db.rollback()
        db.close()
    assert excinfo.value.reason == "freeform_on_auth_account"


def test_a_denial_writes_an_audit_row_with_no_actor(world, live):
    """A blocked send has no logged-in user, which is why QCP has its own log."""
    db = SessionLocal()
    try:
        with pytest.raises(RoutingDenied):
            routing.resolve_route(
                db,
                product_slug=world.product_slug,
                intent="otp_freeform",
                to_phone_e164="+237600000009",
                kind="text",
            )
        db.commit()
        row = (
            db.query(WhatsAppAuditLog)
            .filter(WhatsAppAuditLog.action == "routing.denied")
            .order_by(WhatsAppAuditLog.id.desc())
            .first()
        )
        assert row is not None
        assert row.outcome == "denied"
        assert row.reason == "freeform_on_auth_account"
        assert row.actor_id is None
    finally:
        db.close()


def test_delivery_disabled_is_the_last_gate(world, monkeypatch):
    """Env is a kill switch a database toggle cannot override."""
    whatsapp_world.enable_delivery(monkeypatch, enabled=False)
    db = SessionLocal()
    try:
        with pytest.raises(RoutingDenied) as excinfo:
            routing.resolve_route(
                db,
                product_slug=world.product_slug,
                intent="login_otp",
                to_phone_e164="+237600000009",
                variables=("482913",),
            )
    finally:
        db.rollback()
        db.close()
    assert excinfo.value.reason == "delivery_disabled"
    # Resolved far enough to say what *would* have been sent.
    assert excinfo.value.account_id == world.verify.id
    assert excinfo.value.template_id == world.otp_template.id


def test_variable_arity_mismatch_is_refused(world, live):
    db = SessionLocal()
    try:
        with pytest.raises(RoutingDenied) as excinfo:
            routing.resolve_route(
                db,
                product_slug=world.product_slug,
                intent="login_otp",
                to_phone_e164="+237600000009",
                variables=("482913", "extra"),
            )
    finally:
        db.rollback()
        db.close()
    assert excinfo.value.reason == "variable_arity_mismatch"


# ---------------------------------------------------------------------------
# The purpose assertions, directly
# ---------------------------------------------------------------------------
# The database refuses to store the illegal pairings, so the only way to test
# the resolver's own assertions is to call them with the shapes the storage
# engine will not hold. This is the code that would catch a bug in L1 — or a
# future dialect where a constraint was dropped.

def test_marketing_on_an_authentication_account_raises():
    with pytest.raises(RoutingDenied) as excinfo:
        routing.assert_purpose_compatible(
            account_purpose="authentication",
            template_account_purpose="authentication",
            template_category="marketing",
            kind="template",
        )
    assert excinfo.value.reason == "marketing_on_auth_account"


def test_authentication_template_off_the_verify_number_raises():
    with pytest.raises(RoutingDenied) as excinfo:
        routing.assert_purpose_compatible(
            account_purpose="engagement",
            template_account_purpose="engagement",
            template_category="authentication",
            kind="template",
        )
    assert excinfo.value.reason == "auth_template_off_verify"


def test_template_bound_to_the_other_account_raises():
    with pytest.raises(RoutingDenied) as excinfo:
        routing.assert_purpose_compatible(
            account_purpose="authentication",
            template_account_purpose="engagement",
            template_category="utility",
            kind="template",
        )
    assert excinfo.value.reason == "purpose_mismatch"


def test_utility_on_an_authentication_account_raises():
    """The category that used to fall through both branches.

    ``marketing`` and ``authentication`` were named explicitly and ``utility``
    matched neither, so it was accepted on Verify by omission.
    """
    with pytest.raises(RoutingDenied) as excinfo:
        routing.assert_purpose_compatible(
            account_purpose="authentication",
            template_account_purpose="authentication",
            template_category="utility",
            kind="template",
        )
    assert excinfo.value.reason == "non_auth_template_on_verify"


def test_a_template_send_that_states_no_category_is_refused():
    """L3 sees only the ticket's fields, so an absent category must refuse.

    Returning early on ``template_category is None`` meant a ticket that
    simply omitted its category skipped every remaining rule — the last
    independent layer became an HMAC check and nothing more.
    """
    for account_purpose in ("authentication", "engagement"):
        with pytest.raises(RoutingDenied) as excinfo:
            routing.assert_purpose_compatible(
                account_purpose=account_purpose,
                template_account_purpose=None,
                template_category=None,
                kind="template",
            )
        assert excinfo.value.reason == "missing_template_category"


def test_a_freeform_send_off_verify_still_needs_no_category():
    """Free-form on QUATA carries no template and therefore no category."""
    routing.assert_purpose_compatible(
        account_purpose="engagement",
        template_account_purpose=None,
        template_category=None,
        kind="text",
    )


@pytest.mark.parametrize(
    "account_purpose,template_category",
    [("authentication", "authentication"), ("engagement", "marketing"), ("engagement", "utility")],
)
def test_the_legal_pairings_are_accepted(account_purpose, template_category):
    routing.assert_purpose_compatible(
        account_purpose=account_purpose,
        template_account_purpose=account_purpose,
        template_category=template_category,
        kind="template",
    )


# ---------------------------------------------------------------------------
# L3 — meta.py refuses anything that isn't an authentic, legal ticket
# ---------------------------------------------------------------------------

def _ticket(world, db, intent="login_otp", variables=("482913",), kind="template"):
    return routing.resolve_route(
        db,
        product_slug=world.product_slug,
        intent=intent,
        to_phone_e164="+237600000009",
        kind=kind,
        variables=variables,
    )


def test_meta_sends_a_valid_authentication_ticket(world, live, no_http):
    db = SessionLocal()
    try:
        ticket = _ticket(world, db)
        result = meta.send_template(ticket, db=db)
    finally:
        db.close()
    assert result.ok is True
    assert result.provider_message_id == "wamid.TEST"
    assert len(no_http) == 1
    assert world.verify.phone_number_id in no_http[0]["url"]
    assert no_http[0]["payload"]["template"]["name"] == world.otp_template.name


def test_meta_refuses_a_mutated_ticket_and_issues_no_http(world, live, no_http):
    """Mutating a field without the key breaks the HMAC."""
    db = SessionLocal()
    try:
        ticket = _ticket(world, db)
        forged = dataclasses.replace(ticket, to_phone_e164="+237699999999")
        with pytest.raises(RoutingDenied) as excinfo:
            meta.send_template(forged, db=db)
    finally:
        db.close()
    assert excinfo.value.reason == "invalid_ticket"
    assert no_http == []


def test_meta_refuses_marketing_on_verify_even_with_a_valid_checksum(world, live, no_http):
    """The scenario a bug in L2 — or a rogue in-process caller — would create.

    The ticket is re-signed with the real ``SECRET_KEY``, so the HMAC passes.
    What stops it is ``meta.py`` re-asserting the category rules from the
    ticket's own fields. No HTTP is issued.
    """
    db = SessionLocal()
    try:
        legal = _ticket(world, db, intent="promo_weekend", variables=("2 for 1",))
        assert legal.template_category == "marketing"
        moved = dataclasses.replace(
            legal,
            account_id=world.verify.id,
            account_purpose="authentication",
            phone_number_id=world.verify.phone_number_id,
        )
        forged = dataclasses.replace(moved, checksum=routing.ticket_checksum(moved))
        assert forged.checksum == routing.ticket_checksum(forged)  # authentic…

        with pytest.raises(RoutingDenied) as excinfo:
            meta.send_template(forged, db=db)  # …and still refused
    finally:
        db.close()
    assert excinfo.value.reason == "marketing_on_auth_account"
    assert no_http == []


def test_meta_refuses_a_genuine_authentication_ticket_passed_to_send_text(world, live, no_http):
    """The transport must judge the ticket it is given, not the caller's word.

    Nothing is forged here: this is exactly the ticket ``resolve_route``
    mints for QuataFood's login OTP, and it honestly declares
    ``kind='template'``. ``verify_ticket`` therefore cannot catch it — it
    evaluates ``freeform_on_auth_account`` against the *declared* kind. Only
    ``send_text`` itself is positioned to refuse, and it must, or one line
    inside ``dispatch`` is enough to POST arbitrary prose from Quata Verify.
    """
    db = SessionLocal()
    try:
        genuine = _ticket(world, db)
        assert genuine.kind == "template"
        assert genuine.account_purpose == "authentication"
        assert genuine.checksum == routing.ticket_checksum(genuine)  # authentic…
        with pytest.raises(RoutingDenied) as excinfo:
            meta.send_text(  # …and still refused
                genuine,
                db=db,
                body_text="FLASH SALE! 50% off all QuataFood orders this weekend.",
            )
    finally:
        db.close()
    assert excinfo.value.reason == "freeform_on_auth_account"
    assert no_http == []


def test_meta_send_text_refuses_a_template_ticket_off_verify_too(world, live, no_http):
    """A template ticket is never permission to send free-form, on any number."""
    db = SessionLocal()
    try:
        genuine = _ticket(world, db, intent="order_dispatched", variables=("ORD-1", "18:40"))
        assert genuine.account_purpose == "engagement"
        with pytest.raises(RoutingDenied) as excinfo:
            meta.send_text(genuine, db=db, body_text="hello")
    finally:
        db.close()
    assert excinfo.value.reason == "invalid_ticket"
    assert no_http == []


def test_meta_still_sends_a_genuine_freeform_ticket_from_the_engagement_number(
    world, live, no_http
):
    """The positive control: free-form is legal on QUATA and still works."""
    db = SessionLocal()
    try:
        ticket = _ticket(world, db, intent="support_reply", kind="text", variables=())
        assert ticket.account_id == world.quata.id
        result = meta.send_text(ticket, db=db, body_text="Your order is on its way.")
    finally:
        db.close()
    assert result.ok is True
    assert len(no_http) == 1
    assert world.quata.phone_number_id in no_http[0]["url"]
    assert no_http[0]["payload"]["type"] == "text"


def test_meta_refuses_a_utility_ticket_on_verify_even_with_a_valid_checksum(world, live, no_http):
    """Utility is legal on QUATA and illegal on Verify — re-checked at L3."""
    db = SessionLocal()
    try:
        legal = _ticket(world, db, intent="order_dispatched", variables=("ORD-1", "18:40"))
        assert legal.template_category == "utility"
        moved = dataclasses.replace(
            legal,
            account_id=world.verify.id,
            account_purpose="authentication",
            phone_number_id=world.verify.phone_number_id,
        )
        forged = dataclasses.replace(moved, checksum=routing.ticket_checksum(moved))
        assert forged.checksum == routing.ticket_checksum(forged)  # authentic…

        with pytest.raises(RoutingDenied) as excinfo:
            meta.send_template(forged, db=db)  # …and still refused
    finally:
        db.close()
    assert excinfo.value.reason == "non_auth_template_on_verify"
    assert no_http == []


def test_meta_refuses_a_template_ticket_that_states_no_category(world, live, no_http):
    """The shape that skipped every rule below the early return."""
    db = SessionLocal()
    try:
        legal = _ticket(world, db)
        stripped = dataclasses.replace(legal, template_category=None)
        forged = dataclasses.replace(stripped, checksum=routing.ticket_checksum(stripped))
        with pytest.raises(RoutingDenied) as excinfo:
            meta.send_template(forged, db=db)
    finally:
        db.close()
    assert excinfo.value.reason == "missing_template_category"
    assert no_http == []


def test_meta_refuses_a_hand_built_ticket(world, live, no_http):
    forged = routing.SendTicket(
        ticket_id="deadbeef",
        account_id=world.verify.id,
        account_purpose="authentication",
        phone_number_id=world.verify.phone_number_id,
        template_id=world.otp_template.id,
        template_name=world.otp_template.name,
        template_language="en",
        template_category="authentication",
        product_id=world.product.id,
        intent="login_otp",
        kind="template",
        to_phone_e164="+237600000009",
        variables=("000000",),
        checksum="0" * 64,
    )
    db = SessionLocal()
    try:
        with pytest.raises(RoutingDenied) as excinfo:
            meta.send_template(forged, db=db)
    finally:
        db.close()
    assert excinfo.value.reason == "invalid_ticket"
    assert no_http == []


# ---------------------------------------------------------------------------
# Re-minting a queued row: the template must still belong to the account
# ---------------------------------------------------------------------------

def test_rebuild_ticket_refuses_a_template_registered_on_another_account(world, live):
    """A number migration retires a WABA; its templates stay in the table.

    Purposes match, so the purpose assertions are all satisfied — and the
    live number would be handed a template Meta only knows on the retired
    WABA. Meta rejects it, and the attempt budget pays for it.
    """
    db = SessionLocal()
    retired = WhatsAppAccount(
        slug=f"quata_retired_{world.suffix}",
        name="QUATA (retired)",
        purpose="engagement",
        phone_number_id=f"PN_RETIRED_{world.suffix}",
        waba_id=f"WABA_RETIRED_{world.suffix}",
        display_phone="+237600000003",
        is_active=False,
    )
    try:
        db.add(retired)
        db.flush()
        stray = WhatsAppTemplate(
            account_id=retired.id,
            account_purpose="engagement",
            product_id=world.product.id,
            name=f"tp_stray_{world.suffix}",
            language="en",
            category="utility",
            intent="order_dispatched",
            status="approved",
            variables=["order", "eta"],
        )
        db.add(stray)
        db.flush()

        queued = WhatsAppMessage(
            message_uid=f"stray{world.suffix}",
            account_id=world.quata.id,
            account_purpose="engagement",
            product_id=world.product.id,
            template_id=stray.id,
            direction="outbound",
            kind="template",
            intent="order_dispatched",
            to_phone_e164="+237600000009",
        )
        with pytest.raises(RoutingDenied) as excinfo:
            routing.rebuild_ticket(db, queued, variables=("ORD-1", "18:40"))
    finally:
        db.rollback()
        db.close()
    assert excinfo.value.reason == "template_account_mismatch"


def test_rebuild_ticket_still_re_mints_a_correctly_bound_row(world, live):
    """The positive control for the check above."""
    db = SessionLocal()
    try:
        queued = WhatsAppMessage(
            message_uid=f"good{world.suffix}",
            account_id=world.quata.id,
            account_purpose="engagement",
            product_id=world.product.id,
            template_id=world.order_template.id,
            direction="outbound",
            kind="template",
            intent="order_dispatched",
            to_phone_e164="+237600000009",
        )
        ticket = routing.rebuild_ticket(db, queued, variables=("ORD-1", "18:40"))
    finally:
        db.rollback()
        db.close()
    assert ticket.account_id == world.quata.id
    assert ticket.template_id == world.order_template.id
    assert ticket.checksum == routing.ticket_checksum(ticket)


# ---------------------------------------------------------------------------
# Credentials: from the database, never logged
# ---------------------------------------------------------------------------

def test_the_access_token_never_appears_in_an_error_returned_to_a_caller(world, live, monkeypatch):
    """Meta echoes bad tokens back in its error text. We must not pass that on."""
    from app.services.whatsapp import credentials

    secret = "EAAG_pytest_token_value_do_not_leak"
    db = SessionLocal()
    try:
        account = db.merge(world.verify)
        account.access_token_encrypted = credentials.encrypt_wa_secret(secret)
        db.commit()

        def _explode(request, timeout=None):
            body = json.dumps(
                {"error": {"message": f"Invalid OAuth access token: {secret}", "code": 190}}
            ).encode("utf-8")
            raise urllib.error.HTTPError(
                request.full_url, 401, "Unauthorized", {}, io.BytesIO(body)
            )

        monkeypatch.setattr(meta.urllib.request, "urlopen", _explode)

        ticket = _ticket(world, db)
        result = meta.send_template(ticket, db=db)
    finally:
        db.rollback()
        db.close()

    assert result.ok is False
    assert secret not in (result.error or "")
    assert "***" in (result.error or "")
    assert result.error_code == "190"
    # 401 is our fault, not a blip — retrying would burn attempts.
    assert result.retryable is False


def test_a_credential_round_trips_and_is_only_ever_described_by_length():
    from app.services.whatsapp import credentials

    secret = "EAAG" + "x" * 40
    stored = credentials.encrypt_wa_secret(secret)
    assert stored is not None
    assert secret not in stored
    assert credentials.decrypt_wa_secret(stored) == secret

    described = credentials.describe_secret(stored)
    assert described == {"configured": True, "length": len(secret)}
    assert secret not in json.dumps(described)
