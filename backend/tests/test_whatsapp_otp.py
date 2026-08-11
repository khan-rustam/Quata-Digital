"""OTP confidentiality: no caller-supplied value survives into a row.

``test_whatsapp_idempotency`` already asserts redaction for the one shape the
world happens to declare — a template whose placeholder is literally named
``code``. That is the *lucky* shape. This module asserts the property that
actually has to hold, for the shapes production will really produce:

* Meta's authentication templates are **positional** — ``{{1}}`` — so the
  realistic stored name is ``"1"``, which no deny-list will ever match.
* A template may declare nothing, or declare a different number of names than
  the caller supplied, in which case ``dispatch`` falls back to positional
  names anyway.
* An operator naming the placeholder ``verification``, ``value`` or
  ``number`` picks a name the deny-list does not carry.

and on **both** exits of ``send()``:

* ``queued`` — the happy path;
* ``suppressed`` — which is the outcome of *every* send in the shipped default
  state, because ``WHATSAPP_ENABLED`` is false and routing check 8
  (``delivery_disabled``) is deliberately last so the row still records what
  would have been sent.

The rule under test is not "a secret-looking name is digested". It is: **if the
resolved template's category is ``authentication``, every variable is digested,
whatever it is called.**
"""
from __future__ import annotations

import json
import uuid

import pytest

from app.db.session import SessionLocal, engine
from app.models import Base, WhatsAppMessage, WhatsAppTemplate
from app.services.whatsapp import dispatch, meta, redaction, settings_store

from . import whatsapp_world


OTP = "313373"


# ---------------------------------------------------------------------------
# World
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


@pytest.fixture
def dormant(monkeypatch):
    """The shipped default state, set the way production sets it.

    ``WHATSAPP_ENABLED=False`` is the env kill switch; it short-circuits
    ``delivery_enabled()`` whatever the admin toggle says. Every send in this
    state ends in ``suppressed``.
    """
    from app.core.config import settings as env_settings
    from app.services import site_settings

    monkeypatch.setattr(env_settings, "WHATSAPP_ENABLED", False)
    site_settings.invalidate_cache()
    assert settings_store.delivery_enabled() is False
    yield
    site_settings.invalidate_cache()


@pytest.fixture
def declare(world):
    """Rewrite the OTP template's declared placeholder names, then restore.

    The point of the module: the template's *category* is what decides
    redaction, so the declared names are free to be anything.
    """
    template_id = world.otp_template.id

    def _set(names: list[str]) -> None:
        with SessionLocal() as db:
            db.query(WhatsAppTemplate).filter(WhatsAppTemplate.id == template_id).update(
                {WhatsAppTemplate.variables: list(names)}, synchronize_session=False
            )
            db.commit()

    with SessionLocal() as db:
        original = list((db.get(WhatsAppTemplate, template_id).variables) or [])
    yield _set
    _set(original)


@pytest.fixture
def provider(monkeypatch):
    """Records every request that would have been issued to the Cloud API."""

    class Provider:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def __call__(self, url, *, token, payload=None, method="POST"):
            self.calls.append({"url": url, "payload": payload})
            return True, {"messages": [{"id": f"wamid.{uuid.uuid4().hex}"}]}, None, 200

    stub = Provider()
    monkeypatch.setattr(meta, "_call", stub)
    return stub


def _row(message_uid: str) -> WhatsAppMessage:
    with SessionLocal() as db:
        row = dispatch.get_message(db, message_uid)
        assert row is not None, f"no whatsapp_messages row for {message_uid}"
        db.expunge(row)
        return row


def _assert_nothing_readable(row: WhatsAppMessage, secret: str) -> None:
    stored = row.variables or {}
    assert stored, "an authentication row with variables must still record them, digested"
    assert secret not in json.dumps(stored), f"the caller's value survived into {stored!r}"
    for name, value in stored.items():
        assert isinstance(value, str) and value.startswith("sha256:"), (
            f"variable {name!r} was stored as {value!r}, not a digest"
        )


# ---------------------------------------------------------------------------
# CRITICAL 2 — the queued path
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "declared",
    [
        ["1"],  # Meta's real positional placeholder
        ["verification"],  # reads like a secret, is not on the deny-list
        ["value"],
        ["number"],
        ["code"],  # the lucky shape, kept so the parametrisation is honest
    ],
    ids=["positional", "verification", "value", "number", "code"],
)
def test_a_queued_auth_row_digests_every_variable_whatever_it_is_called(
    world, live, declare, declared
):
    declare(declared)
    result = dispatch.send(
        product_slug=world.product_slug,
        intent="login_otp",
        to_phone_e164="+237600000201",
        variables=(OTP,),
        reference=f"OTP-Q-{uuid.uuid4().hex}",
        dispatch=False,
    )
    assert result["ok"] is True
    assert result["status"] == "queued"
    _assert_nothing_readable(_row(result["message_uid"]), OTP)


def test_the_digest_is_still_comparable_for_support(world, live, declare):
    """Redaction must stay a *digest*, not a wipe — the row is a debugging aid."""
    declare(["1"])
    result = dispatch.send(
        product_slug=world.product_slug,
        intent="login_otp",
        to_phone_e164="+237600000202",
        variables=(OTP,),
        reference=f"OTP-Q-{uuid.uuid4().hex}",
        dispatch=False,
    )
    stored = _row(result["message_uid"]).variables
    assert stored["1"] == redaction.redact_variables({"code": OTP})["code"], (
        "the same code must hash the same way regardless of the placeholder name"
    )


def test_an_engagement_variable_is_still_stored_in_clear(world, live):
    """The fix must be category-driven, not a blanket digest of everything.

    Order and delivery variables are the whole reason the admin console can
    answer "what did we send this customer?".
    """
    result = dispatch.send(
        product_slug=world.product_slug,
        intent="order_dispatched",
        to_phone_e164="+237600000203",
        variables=("ORD-4471", "18:40"),
        reference=f"ORD-{uuid.uuid4().hex}",
        dispatch=False,
    )
    stored = _row(result["message_uid"]).variables
    assert stored == {"order": "ORD-4471", "eta": "18:40"}


# ---------------------------------------------------------------------------
# CRITICAL 1 — the suppressed path, which is the shipped default
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "declared, supplied",
    [
        (["1"], (OTP,)),  # arity matches: denied last, by delivery_disabled
        (["code"], (OTP, "unused")),  # declared names, wrong arity
        ([], (OTP,)),  # template declares nothing at all
        (["verification"], (OTP,)),
    ],
    ids=["positional", "arity_mismatch", "no_names", "innocent_name"],
)
def test_a_suppressed_auth_row_digests_every_variable(
    world, dormant, declare, declared, supplied
):
    declare(declared)
    result = dispatch.send(
        product_slug=world.product_slug,
        intent="login_otp",
        to_phone_e164="+237600000211",
        variables=supplied,
        dispatch=False,
    )
    assert result["status"] == dispatch.STATUS_SUPPRESSED
    assert result["message_uid"] is not None, (
        "the suppressed row must exist — it is what the operator reads during migration"
    )
    _assert_nothing_readable(_row(result["message_uid"]), OTP)


def test_the_default_state_really_is_suppressed(world, dormant, declare):
    """Pins the premise of the test above: dormant is not an edge case."""
    declare(["1"])
    result = dispatch.send(
        product_slug=world.product_slug,
        intent="login_otp",
        to_phone_e164="+237600000212",
        variables=(OTP,),
        dispatch=False,
    )
    assert result["status"] == dispatch.STATUS_SUPPRESSED
    assert result["reason"] == "delivery_disabled"


# ---------------------------------------------------------------------------
# KNOCK-ON — a redacted row can never be re-rendered
# ---------------------------------------------------------------------------

def test_recover_payload_refuses_every_redaction_sentinel():
    """The guard must recognise every *marker* ``redact_variables`` writes.

    Two of them: a ``sha256:`` digest, and the shared redactor's
    ``[redacted]`` for a nested credential. Only the first was recognised.
    """
    db = SessionLocal()
    try:
        for stored in (
            {"1": "sha256:523fa640"},
            {"1": redaction.REDACTED},
            {"order": "ORD-1", "code": redaction.REDACTED},
        ):
            row = WhatsAppMessage(template_id=None, variables=stored, body=None)
            assert dispatch._recover_payload(db, row) is None, (
                f"{stored!r} was treated as re-renderable"
            )
    finally:
        db.close()


# A real Douala restaurant name. "•" is ordinary French copy, not a mask.
BULLET_COPY = "Chez Paul • Douala"


def test_a_bullet_in_ordinary_french_copy_is_not_a_redaction_marker():
    """The recognition rule must be a marker, not a printable character.

    ``mask_identifier`` builds its mask out of "•", but ``redact_variables``
    never emits one for a template variable — masking happens inside
    ``redact`` for maskable keys of a *nested dict*, and template variables
    are scalars. Treating any value containing "•" as redacted therefore had
    no true positives and one very expensive false positive.
    """
    assert redaction.is_redacted_value(BULLET_COPY) is False
    assert redaction.is_redacted_value("•") is False
    assert redaction.is_redacted_value("sha256:523fa640") is True
    assert redaction.is_redacted_value(redaction.REDACTED) is True


def test_a_french_restaurant_name_with_a_bullet_still_reaches_meta(
    world, live, provider
):
    """End to end: a "•" in engagement copy must not kill the send.

    ``payload=None`` is the post-restart / sweeper path, which is where the
    content sniff fired: the variable was read as a masked secret, the send
    was refused as ``payload_not_recoverable``, and the product was told
    nothing.
    """
    result = dispatch.send(
        product_slug=world.product_slug,
        intent="promo_weekend",
        to_phone_e164="+237600000261",
        variables=(BULLET_COPY,),
        reference=f"PROMO-{uuid.uuid4().hex}",
        dispatch=False,
    )
    assert result["status"] == "queued"
    assert _row(result["message_uid"]).variables == {"offer": BULLET_COPY}

    outcome = dispatch.deliver_message(result["message_uid"])

    assert outcome["ok"] is True, f"a bullet killed the send: {outcome!r}"
    assert outcome["status"] == dispatch.STATUS_SENT
    assert BULLET_COPY in json.dumps(provider.calls, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Retrying the dormant backlog — every row QCP ships with is ``suppressed``
# ---------------------------------------------------------------------------

def _send_while_dormant(world, **kwargs) -> dict:
    """One send in the shipped default state, restored before returning."""
    from app.services import site_settings

    with pytest.MonkeyPatch.context() as mp:
        whatsapp_world.enable_delivery(mp, enabled=False)
        assert settings_store.delivery_enabled() is False
        result = dispatch.send(dispatch=False, **kwargs)
    site_settings.invalidate_cache()
    return result


def test_a_suppressed_row_with_named_template_variables_retries(
    world, live, provider
):
    """The first thing operations will do after switching delivery on.

    ``_record_suppressed`` always names variables positionally (``"1"``,
    ``"2"``), but ``_recover_payload`` looked them up by the template's
    declared names (``order``, ``eta``) and dead-lettered the row when they
    were absent — i.e. for every named template in the backlog.
    """
    suppressed = _send_while_dormant(
        world,
        product_slug=world.product_slug,
        intent="order_dispatched",
        to_phone_e164="+237600000271",
        variables=("ORD-9001", "18:40"),
        reference=f"ORD-RETRY-{uuid.uuid4().hex}",
    )
    assert suppressed["status"] == dispatch.STATUS_SUPPRESSED
    assert suppressed["message_uid"] is not None
    assert _row(suppressed["message_uid"]).variables == {"1": "ORD-9001", "2": "18:40"}

    outcome = dispatch.retry_message(suppressed["message_uid"])

    assert outcome["ok"] is True, f"the backlog retry dead-lettered: {outcome!r}"
    assert outcome["status"] == dispatch.STATUS_SENT
    assert len(provider.calls) == 1
    sent = json.dumps(provider.calls[0]["payload"], ensure_ascii=False)
    assert "ORD-9001" in sent and "18:40" in sent
    # Order matters: {{1}} is the order, {{2}} the ETA.
    assert sent.index("ORD-9001") < sent.index("18:40")


def test_a_suppressed_otp_row_still_refuses_to_retry(world, live, declare, provider):
    """Recoverability must not be bought by making OTPs recoverable.

    The dormant backlog contains authentication rows too. Those hold a digest
    and nothing else, so the retry must refuse loudly — never re-render a
    login code out of the database.
    """
    declare(["1"])
    suppressed = _send_while_dormant(
        world,
        product_slug=world.product_slug,
        intent="login_otp",
        to_phone_e164="+237600000272",
        variables=(OTP,),
        reference=f"OTP-RETRY-{uuid.uuid4().hex}",
    )
    assert suppressed["status"] == dispatch.STATUS_SUPPRESSED
    _assert_nothing_readable(_row(suppressed["message_uid"]), OTP)

    outcome = dispatch.retry_message(suppressed["message_uid"])

    assert outcome["ok"] is False
    assert outcome["status"] == dispatch.STATUS_FAILED
    row = _row(suppressed["message_uid"])
    assert row.error_code == "payload_not_recoverable"
    assert row.last_error, "the refusal must say why, not fail silently"
    assert provider.calls == [], "a redacted OTP must not reach Meta at all"
    assert OTP not in json.dumps(provider.calls)


# ---------------------------------------------------------------------------
# Belt and braces — a code on a non-authentication template
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("category", [None, "utility", "marketing", "UTILITY"])
@pytest.mark.parametrize(
    "name, value",
    [
        ("auth_code", "483920"),
        ("security_code", "4839"),
        ("passcode", "83920"),
        ("verify_code", "483920"),
        ("confirmation_code", "483 920"),
    ],
)
def test_a_bare_numeric_code_in_a_secret_ish_name_is_digested_in_any_category(
    category, name, value
):
    """Category is the primary rule; it must not be the only one.

    Nothing forbids an operator wiring a verification code onto a *utility*
    template on the marketing number. The deny-list does not carry
    ``auth_code`` or ``passcode``, so the code was stored in clear.
    """
    out = redaction.redact_variables({name: value}, template_category=category)
    assert out[name].startswith("sha256:"), (
        f"{name}={value!r} was stored in clear on a {category!r} template"
    )
    assert value not in out[name]


def test_ordinary_engagement_variables_stay_readable():
    """The admin console has to be able to answer "what did we send?"."""
    variables = {
        "order": "ORD-4471",
        "order_number": "884471",
        "eta": "18:40",
        "promo_code": "202020",
        "postcode": "237001",
        "offer": BULLET_COPY,
        "amount": "15000",
    }
    assert redaction.redact_variables(dict(variables), template_category="utility") == (
        variables
    )


# ---------------------------------------------------------------------------
# RESIDUAL 1 — the belt-and-braces rule above can never fire on a real row
# ---------------------------------------------------------------------------
#
# The rule tested above keys on the *stored* variable name. Storage renames
# variables to positional "1", "2", "3" before redaction runs:
# ``_record_suppressed`` always does, and QCP ships dormant, so every row it
# holds today is suppressed. ``auth_code`` never reaches ``redact_variables``
# — ``"1"`` does — so the rule matches nothing that exists.
#
# The name is not gone, it was merely dropped on the floor. Two signals
# survive the rename and both are supplied by the caller that did it:
#
#   * ``declared_names`` — the template's own placeholder names, positionally
#     aligned with the values, so a name-based rule can be applied to the name
#     the operator actually chose rather than to the ordinal that replaced it;
#   * ``intent`` — what the *product* asked QCP to send. An operator can
#     mis-categorise a template; the calling product still says ``login_otp``.
#
# Neither is a blanket digest: an ``order_dispatched`` intent with an
# ``order_number`` placeholder stays readable, which is the whole reason
# redaction keys on category in the first place.


@pytest.mark.parametrize(
    "declared, value",
    [
        (["auth_code"], "483920"),
        (["security_code"], "4839"),
        (["passcode"], "83920"),
        (["verification"], "483 920"),
    ],
)
def test_a_positionally_renamed_code_is_digested_from_the_declared_name(
    declared, value
):
    """The live shape: the row says ``{"1": …}``, the template says ``auth_code``."""
    out = redaction.redact_variables(
        {"1": value}, template_category="utility", declared_names=declared
    )
    assert out["1"].startswith("sha256:"), (
        f"a code declared as {declared[0]!r} was stored in clear as {out['1']!r}"
    )
    assert value not in out["1"]


@pytest.mark.parametrize(
    "intent",
    ["login_otp", "password_reset", "verify_email", "2fa_challenge", "LOGIN_OTP"],
)
def test_an_authentication_intent_digests_every_variable(intent):
    """A mis-categorised template does not change what the product asked for.

    ``{{1}}`` is Meta's own placeholder for authentication templates, so
    ``declared_names`` cannot help here — the declared name *is* ``"1"``.
    The intent is the only signal left, and it is the product's, not the
    operator's.
    """
    out = redaction.redact_variables(
        {"1": "483920"},
        template_category="utility",
        intent=intent,
        declared_names=["1"],
    )
    assert out["1"].startswith("sha256:"), (
        f"intent {intent!r} left a code in clear as {out['1']!r}"
    )
    assert "483920" not in out["1"]


def test_engagement_intents_and_names_survive_both_new_signals():
    """The constraint that makes this non-trivial, restated as a test.

    Order ids, ETAs, amounts and promo codes are the reason the admin console
    exists. Neither new signal may digest them.
    """
    variables = {"1": "884471", "2": "18:40", "3": "15000", "4": "202020"}
    declared = ["order_number", "eta", "amount", "promo_code"]
    for intent in ("order_dispatched", "promo_weekend", "support_reply", None):
        assert redaction.redact_variables(
            dict(variables),
            template_category="utility",
            intent=intent,
            declared_names=list(declared),
        ) == variables, f"intent {intent!r} digested ordinary engagement copy"


def test_a_declared_name_of_the_wrong_length_is_ignored():
    """A hint that cannot be aligned is not a hint — never guess an alignment.

    Misaligned names would digest an arbitrary variable, which is exactly the
    "digest everything" answer this must not be.
    """
    out = redaction.redact_variables(
        {"1": "884471", "2": "18:40"},
        template_category="utility",
        declared_names=["auth_code"],
    )
    assert out == {"1": "884471", "2": "18:40"}


def test_a_signal_free_call_is_undecidable_and_dispatch_never_makes_one(
    world, dormant, monkeypatch
):
    """Why the fix is at the call site rather than in the value test.

    ``{"1": "483920"}`` with no intent and no declared names is genuinely
    indistinguishable from ``{"1": "884471"}``, an order number — same
    positional name, same shape, same length. The only rule that would digest
    the first also digests the second, and "order ids and ETAs stay readable"
    is the entire reason redaction keys on category instead of digesting
    everything.

    So the answer is not a cleverer value test. It is that the signal was
    never missing — it was dropped by the caller that renamed the variables —
    and this pins that no path in ``dispatch`` drops it again.
    """
    seen: list[dict] = []
    real = redaction.redact_variables

    def _spy(variables, **kwargs):
        seen.append(kwargs)
        return real(variables, **kwargs)

    monkeypatch.setattr(dispatch, "redact_variables", _spy)
    dispatch.send(
        product_slug=world.product_slug,
        intent="order_dispatched",
        to_phone_e164="+237600000284",
        variables=("ORD-884471", "18:40"),
        dispatch=False,
    )
    assert seen, "no row was redacted at all"
    for kwargs in seen:
        assert kwargs.get("intent"), f"dispatch dropped the intent: {kwargs!r}"
        assert "declared_names" in kwargs, (
            f"dispatch dropped the template's declared names: {kwargs!r}"
        )


def test_a_named_row_is_unaffected_by_its_own_declared_names():
    """When arity matches, the keys already *are* the declared names."""
    out = redaction.redact_variables(
        {"order": "ORD-1", "eta": "18:40"},
        template_category="utility",
        declared_names=["order", "eta"],
    )
    assert out == {"order": "ORD-1", "eta": "18:40"}


# ---------------------------------------------------------------------------
# RESIDUAL 1, end to end — the shape QCP actually holds
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def leaky(world):
    """A utility template on the *engagement* number that carries a code.

    Nothing in QCP forbids this: the DB CHECK only stops a non-authentication
    template sitting on the Verify number. This is the operator mistake the
    residual defect is about, built the way an operator would build it.

    Two of them, because the two signals are independent:

    * ``account_recovery`` declares the placeholder ``auth_code`` — the name
      survives only as ``declared_names``;
    * ``password_reset`` declares Meta's positional ``1`` — only the intent
      the product sent can save it.
    """
    from app.models import WhatsAppRoutingRule

    db = SessionLocal()
    created: list = []
    try:
        for intent, declared in (
            ("account_recovery", ["auth_code"]),
            ("password_reset", ["1"]),
        ):
            template = WhatsAppTemplate(
                account_id=world.quata.id,
                account_purpose="engagement",
                product_id=world.product.id,
                name=f"tp_{intent}_{world.suffix}",
                language="en",
                category="utility",  # the mistake: not `authentication`
                intent=intent,
                status="approved",
                variables=list(declared),
            )
            db.add(template)
            db.flush()
            rule = WhatsAppRoutingRule(
                product_id=world.product.id,
                intent=intent,
                purpose="engagement",
                template_intent=intent,
                locale=None,
                priority=100,
                is_active=True,
                fallback_channel="none",
                conditions={},
            )
            db.add(rule)
            created.extend([template, rule])
        db.commit()
        yield
    finally:
        for obj in created:
            db.delete(obj)
        db.commit()
        db.close()


@pytest.mark.parametrize(
    "intent", ["account_recovery", "password_reset"], ids=["declared_name", "intent"]
)
def test_a_suppressed_utility_row_does_not_store_a_verification_code(
    world, dormant, leaky, intent
):
    """The reproduction, on the path every row in the backlog took.

    ``_record_suppressed`` names variables ``"1"``, ``"2"``, … *before*
    redaction, so the name-based rule had nothing to match and the code
    landed in the database in clear.
    """
    result = dispatch.send(
        product_slug=world.product_slug,
        intent=intent,
        to_phone_e164="+237600000281",
        variables=(OTP,),
        dispatch=False,
    )
    assert result["status"] == dispatch.STATUS_SUPPRESSED
    assert result["message_uid"] is not None
    stored = _row(result["message_uid"]).variables or {}
    assert stored, "the suppressed row must still record that a variable was sent"
    assert OTP not in json.dumps(stored), (
        f"a verification code on a {intent!r} utility template was stored in clear: "
        f"{stored!r}"
    )


def test_a_queued_utility_row_does_not_store_a_verification_code(
    world, live, leaky, monkeypatch
):
    """Same operator mistake once delivery is switched on."""
    monkeypatch.setattr(dispatch, "schedule", lambda *a, **k: None)
    result = dispatch.send(
        product_slug=world.product_slug,
        intent="account_recovery",
        to_phone_e164="+237600000282",
        variables=(OTP,),
        reference=f"REC-{uuid.uuid4().hex}",
        dispatch=False,
    )
    assert result["status"] == "queued"
    stored = _row(result["message_uid"]).variables or {}
    assert OTP not in json.dumps(stored), f"stored in clear: {stored!r}"


def test_the_engagement_backlog_is_still_readable_and_still_retryable(
    world, live, provider
):
    """The regression this must not cause, pinned on the same path.

    If the fix over-reaches, every suppressed engagement row becomes a digest
    — unreadable in the admin console *and* undeliverable, because
    ``_recover_payload`` refuses any row holding a marker.
    """
    suppressed = _send_while_dormant(
        world,
        product_slug=world.product_slug,
        intent="order_dispatched",
        to_phone_e164="+237600000283",
        variables=("ORD-884471", "18:40"),
        reference=f"ORD-READ-{uuid.uuid4().hex}",
    )
    assert _row(suppressed["message_uid"]).variables == {
        "1": "ORD-884471",
        "2": "18:40",
    }
    outcome = dispatch.retry_message(suppressed["message_uid"])
    assert outcome["ok"] is True, f"the engagement backlog stopped retrying: {outcome!r}"


def test_recover_payload_still_rebuilds_a_clean_engagement_row():
    db = SessionLocal()
    try:
        row = WhatsAppMessage(
            template_id=None, variables={"order": "ORD-1", "eta": "18:40"}, body=None
        )
        assert dispatch._recover_payload(db, row) == {
            "variables": ["ORD-1", "18:40"],
            "body": None,
        }
    finally:
        db.close()


def test_the_sweeper_cannot_re_send_a_positional_otp_after_a_restart(
    world, live, declare, provider
):
    """The documented protection, on the shape that actually ships.

    With the code stored in clear the ``sha256:`` guard never fired, so the
    sweeper happily re-rendered a live OTP out of the database and sent it
    late. Delivering it must be refused instead, so the product falls back on
    the channel its routing rule names.
    """
    declare(["1"])
    result = dispatch.send(
        product_slug=world.product_slug,
        intent="login_otp",
        to_phone_e164="+237600000221",
        variables=(OTP,),
        reference=f"OTP-SWEEP-{uuid.uuid4().hex}",
        dispatch=False,
    )
    assert result["status"] == "queued"

    # payload=None is the post-restart case: the RQ job body is gone and only
    # the row survives. This is exactly what sweep_pending() does.
    outcome = dispatch.deliver_message(result["message_uid"])

    assert outcome["ok"] is False
    assert outcome["status"] == dispatch.STATUS_FAILED
    assert _row(result["message_uid"]).error_code == "payload_not_recoverable"
    assert provider.calls == [], "an unrecoverable OTP must not reach Meta at all"
    assert OTP not in json.dumps(provider.calls)


# ---------------------------------------------------------------------------
# HOLE 4 — a reused explicit key must not cross numbers
# ---------------------------------------------------------------------------

def test_a_reused_reference_across_two_numbers_does_not_swallow_the_otp(
    world, live, monkeypatch
):
    """One business reference, two purposes, two numbers — two messages.

    ``{"ok": true, "duplicate": true}`` pointing at the marketing row is the
    worst possible answer: the caller is told the login code was sent, and no
    OTP row exists at all.
    """
    monkeypatch.setattr(dispatch, "schedule", lambda *a, **k: None)
    shared = f"order-{uuid.uuid4().hex[:8]}"
    phone = "+237600000231"

    promo = dispatch.send(
        product_slug=world.product_slug,
        intent="promo_weekend",
        to_phone_e164=phone,
        variables=("2-for-1",),
        idempotency_key=shared,
    )
    otp = dispatch.send(
        product_slug=world.product_slug,
        intent="login_otp",
        to_phone_e164=phone,
        variables=(OTP,),
        idempotency_key=shared,
    )

    assert promo["ok"] is True and promo["duplicate"] is False
    assert otp["duplicate"] is False, "the OTP was swallowed by the marketing row"
    assert otp["message_uid"] != promo["message_uid"]

    with SessionLocal() as db:
        otp_rows = (
            db.query(WhatsAppMessage)
            .filter(
                WhatsAppMessage.account_id == world.verify.id,
                WhatsAppMessage.to_phone_e164 == phone,
            )
            .all()
        )
        assert len(otp_rows) == 1
        assert otp_rows[0].account_purpose == "authentication"
        _assert_nothing_readable(otp_rows[0], OTP)


def test_a_reused_reference_across_two_recipients_is_not_a_duplicate(
    world, live, monkeypatch
):
    """Same product, same intent, same key — different person.

    Namespacing by recipient is what stops one person's OTP answering for
    another's.
    """
    monkeypatch.setattr(dispatch, "schedule", lambda *a, **k: None)
    shared = f"login-{uuid.uuid4().hex[:8]}"

    first = dispatch.send(
        product_slug=world.product_slug,
        intent="login_otp",
        to_phone_e164="+237600000241",
        variables=("111111",),
        idempotency_key=shared,
    )
    second = dispatch.send(
        product_slug=world.product_slug,
        intent="login_otp",
        to_phone_e164="+237600000242",
        variables=("222222",),
        idempotency_key=shared,
    )
    assert first["duplicate"] is False
    assert second["duplicate"] is False
    assert first["message_uid"] != second["message_uid"]


def test_the_same_key_to_the_same_person_still_dedupes(world, live, monkeypatch):
    """The property the explicit key exists for must survive the fix."""
    monkeypatch.setattr(dispatch, "schedule", lambda *a, **k: None)
    shared = f"retry-{uuid.uuid4().hex[:8]}"

    first = dispatch.send(
        product_slug=world.product_slug,
        intent="login_otp",
        to_phone_e164="+237600000251",
        variables=("333333",),
        idempotency_key=shared,
    )
    second = dispatch.send(
        product_slug=world.product_slug,
        intent="login_otp",
        to_phone_e164="+237600000251",
        variables=("333333",),
        idempotency_key=shared,
    )
    assert first["duplicate"] is False
    assert second["duplicate"] is True
    assert second["message_uid"] == first["message_uid"]


# ---------------------------------------------------------------------------
# The clear code travels with the job — so the job must not outlive the code
# ---------------------------------------------------------------------------

def test_the_queued_job_carrying_the_clear_code_is_given_a_short_ttl(monkeypatch):
    """``schedule`` puts the OTP in Redis; RQ's defaults would keep it a year.

    ``payload`` carries the clear variables because the row deliberately does
    not (see ``schedule``'s docstring). That is only tolerable if the job
    expires: RQ defaults to ``ttl=None`` (a queued job waits forever) and
    ``failure_ttl=31536000``, so a job that failed would keep a live login
    code in the failed registry for a year.
    """
    seen: dict = {}

    class _Queue:
        def enqueue(self, func, *args, **kwargs):
            seen["args"] = args
            seen["kwargs"] = kwargs
            return object()

    monkeypatch.setattr(
        "app.services.queue._get_queue", lambda: _Queue(), raising=True
    )
    dispatch.schedule("uid-ttl-1", {"variables": ["313373"]})

    assert seen["args"] == ("uid-ttl-1", {"variables": ["313373"]})
    kwargs = seen["kwargs"]
    # Bounded in every direction a job's arguments can survive.
    assert 0 < kwargs["ttl"] <= 900
    assert 0 < kwargs["failure_ttl"] <= 900
    assert kwargs["result_ttl"] == 0
