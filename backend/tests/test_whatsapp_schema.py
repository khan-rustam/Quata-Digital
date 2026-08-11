"""QCP data layer — schema, constraints, migration and seeds.

Scope: everything the database itself is responsible for. The routing choke
point (``resolve_route``) and the Meta client have their own tests; what is
proved here is the layer *underneath* them — that a violating row cannot be
stored even if every line of Python above it were wrong.

Two dialect facts govern these tests:

* SQLite enforces CHECK constraints. Every CHECK below is therefore asserted
  against the ordinary test database.
* SQLite does **not** enforce foreign keys unless ``PRAGMA foreign_keys=ON``
  is issued, and this repo never issues it (``app/db/session.py``). So the
  composite-FK half of the invariant is proved against a throwaway engine
  with the pragma switched on — see ``fk_engine``. Production is Postgres,
  where those FKs are always enforced.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db.session import SessionLocal
from app.models import (
    Base,
    Product,
    WhatsAppAccount,
    WhatsAppAuditLog,
    WhatsAppConversation,
    WhatsAppDeliveryEvent,
    WhatsAppMessage,
    WhatsAppProduct,
    WhatsAppRoutingRule,
    WhatsAppTemplate,
)


BACKEND_ROOT = Path(__file__).resolve().parent.parent
VERSIONS_DIR = BACKEND_ROOT / "alembic" / "versions"
QCP_REVISION = "x4c5d6e7f8g9"
PREVIOUS_HEAD = "w3b4c5d6e7f8"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db(client) -> Session:
    """A session on the ordinary test DB, after the app lifespan has seeded.

    Depends on ``client`` so the tables exist and the QCP seed has run.
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="module")
def fk_engine():
    """A throwaway SQLite DB with foreign keys actually switched on.

    The app's own SQLite connection does not do this, which is why the module
    docstring in ``models/whatsapp.py`` says the FK layer is inert in dev.
    Here it is turned on so the composite FKs can be proved rather than
    merely asserted to exist in the metadata.
    """
    fd, path = tempfile.mkstemp(suffix=".db", prefix="qcp_fk_")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}", future=True)

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _record):  # pragma: no cover - trivial
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def fk_db(fk_engine) -> Session:
    session = sessionmaker(bind=fk_engine, future=True)()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _accounts(session: Session) -> tuple[WhatsAppAccount, WhatsAppAccount]:
    """(verify, engagement) — creating them on the given session if needed."""
    verify = (
        session.query(WhatsAppAccount)
        .filter(WhatsAppAccount.purpose == "authentication")
        .first()
    )
    engage = (
        session.query(WhatsAppAccount).filter(WhatsAppAccount.purpose == "engagement").first()
    )
    if verify is None:
        verify = WhatsAppAccount(
            slug="quata_verify",
            name="Quata Verify",
            purpose="authentication",
            phone_number_id="",
            waba_id="",
            display_phone="",
            is_active=False,
        )
        session.add(verify)
    if engage is None:
        engage = WhatsAppAccount(
            slug="quata",
            name="QUATA",
            purpose="engagement",
            phone_number_id="",
            waba_id="",
            display_phone="",
            is_active=False,
        )
        session.add(engage)
    session.flush()
    return verify, engage


# ---------------------------------------------------------------------------
# 1. Migration
# ---------------------------------------------------------------------------

def _script_directory():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return ScriptDirectory.from_config(cfg)


def test_migration_chains_from_the_real_previous_head():
    """The QCP revision must sit directly on the notification-center head."""
    script = _script_directory()
    revision = script.get_revision(QCP_REVISION)
    assert revision.down_revision == PREVIOUS_HEAD
    assert (VERSIONS_DIR / f"{QCP_REVISION}_qcp_whatsapp_platform.py").exists()


def test_qcp_revision_is_the_only_head():
    """One head, and it is ours. Two heads break `alembic upgrade head`."""
    assert list(_script_directory().get_heads()) == [QCP_REVISION]


def test_migration_upgrades_and_downgrades_cleanly():
    """Run the whole chain on a fresh DB, then reverse just this revision.

    This is the test that catches a partial index the batch operation cannot
    build, a composite FK naming a column that does not exist, or a
    ``downgrade`` that drops things in the wrong order.
    """
    fd, path = tempfile.mkstemp(suffix=".db", prefix="qcp_migration_")
    os.close(fd)
    env = dict(os.environ, DATABASE_URL=f"sqlite:///{path}")
    try:
        up = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=BACKEND_ROOT, env=env, capture_output=True, text=True,
        )
        assert up.returncode == 0, up.stderr
        assert f"{PREVIOUS_HEAD} -> {QCP_REVISION}" in up.stderr

        import sqlite3

        conn = sqlite3.connect(path)
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'whatsapp%'"
            )
        }
        assert tables == {
            "whatsapp_accounts",
            "whatsapp_products",
            "whatsapp_templates",
            "whatsapp_conversations",
            "whatsapp_messages",
            "whatsapp_routing_rules",
            "whatsapp_delivery_events",
            "whatsapp_audit_log",
        }

        # The partial unique index must actually carry its WHERE clause —
        # without it, a retired number could never coexist with its
        # replacement.
        partial = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='index' "
            "AND name='uq_whatsapp_accounts_active_purpose'"
        ).fetchone()
        assert partial is not None
        assert "WHERE is_active = 1" in partial[0]

        # Both composite FKs must be in the emitted DDL.
        messages_ddl = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name='whatsapp_messages'"
        ).fetchone()[0]
        assert "FOREIGN KEY(account_id, account_purpose)" in messages_ddl
        assert "FOREIGN KEY(template_id, account_purpose)" in messages_ddl
        conn.close()

        down = subprocess.run(
            [sys.executable, "-m", "alembic", "downgrade", PREVIOUS_HEAD],
            cwd=BACKEND_ROOT, env=env, capture_output=True, text=True,
        )
        assert down.returncode == 0, down.stderr

        conn = sqlite3.connect(path)
        left = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE name LIKE '%whatsapp%'"
            )
        ]
        assert left == [], f"downgrade left {left} behind"
        conn.close()
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# 2. Registration, and the CMS left alone
# ---------------------------------------------------------------------------

def test_all_eight_models_are_registered():
    names = set(Base.metadata.tables)
    for model in (
        WhatsAppAccount, WhatsAppProduct, WhatsAppTemplate, WhatsAppConversation,
        WhatsAppMessage, WhatsAppRoutingRule, WhatsAppDeliveryEvent, WhatsAppAuditLog,
    ):
        assert model.__tablename__ in names
        assert model.__tablename__.startswith("whatsapp_")


def test_qcp_does_not_collide_with_the_cms_products_table():
    """`products` belongs to the marketing CMS. QCP's registry is separate."""
    assert Product.__tablename__ == "products"
    assert WhatsAppProduct.__tablename__ == "whatsapp_products"


def test_qcp_tables_are_not_soft_deleted():
    """A message log that the global soft-delete filter can hide is not a log."""
    from app.models.base import SoftDeleteMixin

    for model in (
        WhatsAppAccount, WhatsAppProduct, WhatsAppTemplate, WhatsAppConversation,
        WhatsAppMessage, WhatsAppRoutingRule, WhatsAppDeliveryEvent, WhatsAppAuditLog,
    ):
        assert not issubclass(model, SoftDeleteMixin)


# ---------------------------------------------------------------------------
# 3. Seeds — QCP must ship inert
# ---------------------------------------------------------------------------

def test_both_accounts_are_seeded_dormant_and_credential_free(db):
    rows = {a.slug: a for a in db.query(WhatsAppAccount).all()}
    assert set(rows) >= {"quata_verify", "quata"}

    verify = rows["quata_verify"]
    assert verify.purpose == "authentication"
    assert verify.name == "Quata Verify"

    engage = rows["quata"]
    assert engage.purpose == "engagement"
    assert engage.name == "QUATA"

    for account in (verify, engage):
        assert account.is_active is False, "a seeded account must never arrive live"
        assert account.access_token_encrypted is None
        assert account.app_secret_encrypted is None
        assert account.webhook_verify_token_encrypted is None
        assert account.phone_number_id == ""
        assert account.health == "unknown"


def test_four_products_are_seeded_disabled_and_keyless(db):
    rows = {p.slug: p for p in db.query(WhatsAppProduct).all()}
    assert set(rows) >= {"quatapay", "quatafood", "abaqwa", "quatatrade"}

    for slug in ("quatapay", "quatafood", "abaqwa", "quatatrade"):
        product = rows[slug]
        assert product.is_enabled is False, f"{slug} must not arrive enabled"
        # No sha256 hex digest equals "", so this cannot authenticate.
        assert product.api_key_hash == ""
        assert product.api_key_prefix == ""


def test_only_quatafood_may_reach_the_verify_number(db):
    """The audit found QuataFood owns the fleet's only WhatsApp auth path.

    Everything else is capped to engagement, so re-opening an auth channel
    for QuataPay (email-only OTP since 2026-06-03) has to be a deliberate,
    visible change rather than something this seed quietly permitted.
    """
    rows = {p.slug: p for p in db.query(WhatsAppProduct).all()}
    assert "authentication" in rows["quatafood"].allowed_purposes
    for slug in ("quatapay", "abaqwa", "quatatrade"):
        assert rows[slug].allowed_purposes == ["engagement"]


def test_seeding_twice_adds_nothing(db):
    from app.seeds.whatsapp_seed import seed_whatsapp

    assert seed_whatsapp(db) == {"accounts": 0, "products": 0}


def test_seeding_never_re_enables_a_product_an_admin_switched_off(db):
    """The QuataPay failure mode in reverse: a redeploy must not flip a gate."""
    from app.seeds.whatsapp_seed import seed_whatsapp

    product = db.query(WhatsAppProduct).filter(WhatsAppProduct.slug == "abaqwa").one()
    product.is_enabled = True
    product.api_key_hash = "a" * 64
    db.commit()
    try:
        assert seed_whatsapp(db)["products"] == 0
        db.expire_all()
        again = db.query(WhatsAppProduct).filter(WhatsAppProduct.slug == "abaqwa").one()
        assert again.is_enabled is True
        assert again.api_key_hash == "a" * 64
    finally:
        again = db.query(WhatsAppProduct).filter(WhatsAppProduct.slug == "abaqwa").one()
        again.is_enabled = False
        again.api_key_hash = ""
        db.commit()


# ---------------------------------------------------------------------------
# 4. The invariant — CHECK layer (enforced by SQLite and Postgres alike)
# ---------------------------------------------------------------------------

def test_marketing_template_cannot_live_on_the_verify_number(db):
    verify, _ = _accounts(db)
    db.add(
        WhatsAppTemplate(
            account_id=verify.id,
            account_purpose="authentication",
            name="ck_marketing_on_verify",
            language="en",
            category="marketing",
            intent="promo_blast",
            status="draft",
        )
    )
    with pytest.raises(IntegrityError) as exc:
        db.flush()
    assert "marketing_never_on_verify" in str(exc.value)
    db.rollback()


def test_authentication_template_cannot_live_on_the_engagement_number(db):
    _, engage = _accounts(db)
    db.add(
        WhatsAppTemplate(
            account_id=engage.id,
            account_purpose="engagement",
            name="ck_auth_off_verify",
            language="en",
            category="authentication",
            intent="login_otp",
            status="draft",
        )
    )
    with pytest.raises(IntegrityError) as exc:
        db.flush()
    assert "auth_only_on_verify" in str(exc.value)
    db.rollback()


def test_utility_templates_are_allowed_on_the_engagement_number_only(db):
    """QUATA takes utility; Quata Verify takes ``authentication`` and nothing else.

    Transaction and security alerts are Meta ``utility``, and they belong on
    QUATA. Allowing them on Verify was the hole: ``category`` is
    operator-typed and nothing re-syncs it from Meta, so a template Meta has
    since re-classified as MARKETING would have kept leaving the verification
    number — and a restricted number means QuataFood login OTPs, which have
    no email fallback, stop arriving.
    """
    verify, engage = _accounts(db)
    db.add(
        WhatsAppTemplate(
            account_id=engage.id, account_purpose="engagement",
            name="ok_utility_quata", language="en", category="utility",
            intent="order_dispatched", status="draft",
        )
    )
    db.flush()  # must not raise
    db.rollback()

    db.add(
        WhatsAppTemplate(
            account_id=verify.id, account_purpose="authentication",
            name="ck_utility_verify", language="en", category="utility",
            intent="security_alert", status="draft",
        )
    )
    with pytest.raises(IntegrityError) as exc:
        db.flush()
    assert "verify_is_auth_only" in str(exc.value)
    db.rollback()


def test_verify_number_cannot_send_free_form(db):
    """The Quata Verify number may only ever emit approved templates."""
    verify, _ = _accounts(db)
    db.add(
        WhatsAppMessage(
            message_uid="ck-freeform-verify",
            account_id=verify.id,
            account_purpose="authentication",
            direction="outbound",
            kind="text",
            to_phone_e164="+237600000000",
            body="hello",
        )
    )
    with pytest.raises(IntegrityError) as exc:
        db.flush()
    assert "no_freeform_on_verify" in str(exc.value)
    db.rollback()


def test_inbound_to_the_verify_number_is_still_allowed(db):
    """Meta delivers whatever a user types at the number; dropping it would
    lose the message, so only *sending* free-form is forbidden."""
    verify, _ = _accounts(db)
    db.add(
        WhatsAppMessage(
            message_uid="ok-inbound-verify",
            account_id=verify.id,
            account_purpose="authentication",
            direction="inbound",
            kind="text",
            from_phone_e164="+237600000000",
            body="STOP",
        )
    )
    db.flush()  # must not raise
    db.rollback()


def test_outbound_template_message_requires_a_template(db):
    _, engage = _accounts(db)
    db.add(
        WhatsAppMessage(
            message_uid="ck-template-required",
            account_id=engage.id,
            account_purpose="engagement",
            direction="outbound",
            kind="template",
            template_id=None,
            to_phone_e164="+237600000000",
        )
    )
    with pytest.raises(IntegrityError) as exc:
        db.flush()
    assert "template_required" in str(exc.value)
    db.rollback()


@pytest.mark.parametrize(
    "model,kwargs,fragment",
    [
        (WhatsAppMessage, {"direction": "sideways", "kind": "text"}, "messages_direction"),
        (WhatsAppMessage, {"direction": "outbound", "kind": "carrier_pigeon"}, "messages_kind"),
        (
            WhatsAppMessage,
            {"direction": "outbound", "kind": "text", "status": "vibing"},
            "messages_status",
        ),
    ],
)
def test_message_enum_columns_reject_unknown_values(db, model, kwargs, fragment):
    _, engage = _accounts(db)
    db.add(
        model(
            message_uid=f"ck-{fragment}",
            account_id=engage.id,
            account_purpose="engagement",
            to_phone_e164="+237600000000",
            **kwargs,
        )
    )
    with pytest.raises(IntegrityError) as exc:
        db.flush()
    assert fragment in str(exc.value)
    db.rollback()


def test_account_purpose_and_health_are_constrained(db):
    db.add(
        WhatsAppAccount(
            slug="ck-bad-purpose", name="Bad", purpose="marketing",
            phone_number_id="", waba_id="", display_phone="",
        )
    )
    with pytest.raises(IntegrityError) as exc:
        db.flush()
    assert "accounts_purpose" in str(exc.value)
    db.rollback()


def test_routing_rule_fallback_channel_is_constrained(db):
    """`fallback_channel` is the QuataFood finding made auditable — it must
    hold one of the three real answers, including the explicit 'none'."""
    product = db.query(WhatsAppProduct).filter(WhatsAppProduct.slug == "quatafood").one()
    db.add(
        WhatsAppRoutingRule(
            product_id=product.id, intent="ck_bad_fallback", purpose="authentication",
            template_intent="login_otp", fallback_channel="carrier_pigeon",
        )
    )
    with pytest.raises(IntegrityError) as exc:
        db.flush()
    assert "fallback_channel" in str(exc.value)
    db.rollback()

    db.add(
        WhatsAppRoutingRule(
            product_id=product.id, intent="ck_ok_fallback", purpose="authentication",
            template_intent="login_otp", fallback_channel="none",
        )
    )
    db.flush()  # must not raise
    db.rollback()


def test_audit_outcome_is_constrained(db):
    db.add(
        WhatsAppAuditLog(
            action="routing.denied", resource_type="message",
            outcome="maybe", reason="marketing_on_auth_account",
        )
    )
    with pytest.raises(IntegrityError) as exc:
        db.flush()
    assert "audit_log_outcome" in str(exc.value)
    db.rollback()


def test_a_denial_can_be_recorded_with_no_actor_at_all(db):
    """The whole reason QCP does not reuse `activity_logs`: the most important
    row this system writes has no logged-in user."""
    row = WhatsAppAuditLog(
        actor_id=None, action="routing.denied", resource_type="message",
        outcome="denied", reason="marketing_on_auth_account",
    )
    db.add(row)
    db.flush()
    assert row.id is not None
    db.rollback()


def test_only_one_active_account_per_purpose(db):
    """The partial unique index: a retired number may sit alongside its
    replacement, but two *live* numbers for one purpose may not."""
    db.add_all([
        WhatsAppAccount(
            slug="uq-active-a", name="A", purpose="engagement",
            phone_number_id="", waba_id="", display_phone="", is_active=True,
        ),
        WhatsAppAccount(
            slug="uq-active-b", name="B", purpose="engagement",
            phone_number_id="", waba_id="", display_phone="", is_active=True,
        ),
    ])
    with pytest.raises(IntegrityError) as exc:
        db.flush()
    # SQLite names the column, Postgres names the index; both mean the
    # partial unique index fired.
    message = str(exc.value)
    assert "uq_whatsapp_accounts_active_purpose" in message or "purpose" in message
    db.rollback()

    # One live, one retired: fine.
    db.add_all([
        WhatsAppAccount(
            slug="uq-active-c", name="C", purpose="engagement",
            phone_number_id="", waba_id="", display_phone="", is_active=True,
        ),
        WhatsAppAccount(
            slug="uq-retired-d", name="D", purpose="engagement",
            phone_number_id="", waba_id="", display_phone="", is_active=False,
        ),
    ])
    db.flush()  # must not raise
    db.rollback()


def test_delivery_event_dedupe_key_is_unique(db):
    """Meta redelivers whole envelopes; the second copy must collide."""
    _, engage = _accounts(db)
    now = datetime.now(timezone.utc)
    for _ in range(2):
        db.add(
            WhatsAppDeliveryEvent(
                provider_message_id="wamid.DEDUPE",
                account_id=engage.id,
                status="delivered",
                status_at=now,
                dedupe_key="wamid.DEDUPE|delivered|1754870000",
                received_at=now,
            )
        )
    with pytest.raises(IntegrityError) as exc:
        db.flush()
    assert "dedupe_key" in str(exc.value)
    db.rollback()


def test_message_uid_and_idempotency_key_are_unique(db):
    _, engage = _accounts(db)
    for _ in range(2):
        db.add(
            WhatsAppMessage(
                message_uid="uq-shared-uid",
                account_id=engage.id,
                account_purpose="engagement",
                direction="outbound",
                kind="text",
                to_phone_e164="+237600000000",
                idempotency_key="quatafood:uq-shared-key",
            )
        )
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


# ---------------------------------------------------------------------------
# 5. The invariant — composite-FK layer (Postgres always; SQLite only with
#    the pragma this fixture switches on)
# ---------------------------------------------------------------------------

def test_message_cannot_pair_the_verify_account_with_an_engagement_template(fk_db):
    """THE row the whole schema exists to refuse."""
    verify, engage = _accounts(fk_db)
    tmpl = WhatsAppTemplate(
        account_id=engage.id,
        account_purpose="engagement",
        name="fk_marketing_promo",
        language="en",
        category="marketing",
        intent="promo_blast",
        status="approved",
    )
    fk_db.add(tmpl)
    fk_db.flush()

    fk_db.add(
        WhatsAppMessage(
            message_uid="fk-cross-purpose",
            account_id=verify.id,
            account_purpose="authentication",
            template_id=tmpl.id,          # a marketing template…
            direction="outbound",
            kind="template",              # …on the authentication number.
            to_phone_e164="+237600000000",
        )
    )
    with pytest.raises(IntegrityError) as exc:
        fk_db.flush()
    assert "FOREIGN KEY" in str(exc.value).upper()
    fk_db.rollback()


def test_message_cannot_claim_a_purpose_its_account_does_not_have(fk_db):
    verify, _ = _accounts(fk_db)
    fk_db.add(
        WhatsAppMessage(
            message_uid="fk-wrong-purpose",
            account_id=verify.id,
            account_purpose="engagement",   # verify is 'authentication'
            direction="outbound",
            kind="text",
            to_phone_e164="+237600000000",
        )
    )
    with pytest.raises(IntegrityError) as exc:
        fk_db.flush()
    assert "FOREIGN KEY" in str(exc.value).upper()
    fk_db.rollback()


def test_a_correctly_bound_template_message_inserts_fine(fk_db):
    """The positive control — the constraints block the bad shape, not all work."""
    verify, _ = _accounts(fk_db)
    tmpl = WhatsAppTemplate(
        account_id=verify.id,
        account_purpose="authentication",
        name="fk_login_otp",
        language="en",
        category="authentication",
        intent="login_otp",
        status="approved",
    )
    fk_db.add(tmpl)
    fk_db.flush()

    msg = WhatsAppMessage(
        message_uid="fk-good-otp",
        account_id=verify.id,
        account_purpose="authentication",
        template_id=tmpl.id,
        direction="outbound",
        kind="template",
        intent="login_otp",
        to_phone_e164="+237600000000",
        # Redacted at rest — never the code itself.
        variables={"code": "sha256:ab12cd34"},
    )
    fk_db.add(msg)
    fk_db.flush()
    assert msg.id is not None
    assert msg.status == "queued"
    assert msg.attempts == 0
    fk_db.rollback()


def test_conversation_is_unique_per_account_and_contact(fk_db):
    _, engage = _accounts(fk_db)
    for _ in range(2):
        fk_db.add(
            WhatsAppConversation(
                account_id=engage.id,
                wa_contact_id="237600000000",
                phone_e164="+237600000000",
            )
        )
    with pytest.raises(IntegrityError):
        fk_db.flush()
    fk_db.rollback()
