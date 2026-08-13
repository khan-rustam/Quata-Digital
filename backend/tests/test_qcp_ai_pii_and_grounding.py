"""Round 6 — what leaves the country, and what may be said when nothing was looked up.

Three defects, one file, because they are the same defect seen from three
sides: the layer knows nothing about the customer, sends everything the
customer typed to a third party abroad, and then decides what it may say
using a list of words.

**1. PII leaving Cameroon.** ``_build_prompts`` embedded the customer's
message *verbatim* in the prompt sent to OpenAI in the United States. A
customer who types their CNI number, their MoMo number or their card number
had all of it forwarded. Nothing in ``classify``, ``provider`` or ``respond``
redacted anything. The tests below assert the redaction happens on the way
**in**, before the model is called, and — just as importantly — that a
reference to a *thing* (an order number) survives, because a layer that
masks "ma commande 4417" into "ma commande [id]" can no longer help anyone.

**2. "No facts, no claims" was unproven.** The rule was the right shape and
the implementation was still lexical: a possessive next to a noun from a
list. Two phrasings walk through it — a decision stated with no possessive
("le dossier est en regle"), and the customer's own words quoted back. The
tests here are an *allow-list* test: with zero facts the reply must match one
of a small set of safe shapes, and anything unrecognised is refused. That
inverts the game — a new synonym no longer wins, because being unlisted is
now a refusal rather than a pass.

**3. The AI cannot look anything up.** There is no seam a product can
implement, so ``facts`` is hard-coded empty at every call site. The tests
below pin the contract, the null default (which is the correct behaviour
today — no product is connected to QCP), and the property that makes defect 2
real rather than theoretical: a source that returns nothing, or explodes,
leaves the reply with nothing it is allowed to claim.

French **and** English throughout. Cameroon is both, and a defence tested in
one language is not tested.

Every test in the first two sections was observed failing before
``ai/pii.py``, ``ai/facts.py`` and the new output gate existed.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.db.session import SessionLocal
from app.models import WhatsAppAccount, WhatsAppConversation, WhatsAppProduct
from app.services.whatsapp import handover, settings_store
from app.services.whatsapp.ai import facts as fact_seam
from app.services.whatsapp.ai import pii, provider, respond, turn


SUFFIX = uuid.uuid4().hex[:8]


# ---------------------------------------------------------------------------
# World — same shape as the other QCP AI suites: both numbers inactive, so
# this module cannot collide with another module's world on
# ``uq_whatsapp_accounts_active_purpose``. Nothing here reaches a network.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def world(app_instance):
    from fastapi.testclient import TestClient

    from app.services.whatsapp.credentials import encrypt_wa_secret

    with TestClient(app_instance):
        with SessionLocal() as db:
            token = encrypt_wa_secret(f"PYTEST_NOT_A_REAL_TOKEN_{SUFFIX}")
            engagement = WhatsAppAccount(
                slug=f"pii-quata-{SUFFIX}",
                name="QUATA (pii)",
                purpose="engagement",
                phone_number_id=f"PN-PII-ENG-{SUFFIX}",
                waba_id=f"WABA-PII-ENG-{SUFFIX}",
                display_phone="+237600007701",
                api_version="v21.0",
                access_token_encrypted=token,
                is_active=False,
                health="unknown",
            )
            product = WhatsAppProduct(
                slug=f"pii-food-{SUFFIX}",
                name="PII Food",
                is_enabled=True,
                api_key_hash="3" * 64,
                api_key_prefix="qcp_pii_test",
                allowed_purposes=["engagement"],
                default_locale="fr",
            )
            db.add_all([engagement, product])
            db.commit()
            ids = {
                "engagement_id": engagement.id,
                "product_id": product.id,
                "product_slug": product.slug,
            }
    yield ids


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session
        session.rollback()


def _switches(monkeypatch, *, ai_env=True, fleet=True, toggle=True, key=True) -> None:
    from app.core.config import settings as env_settings
    from app.services import site_settings

    monkeypatch.setenv(settings_store.ENV_AI_REPLIES, "true" if ai_env else "false")
    monkeypatch.setattr(env_settings, "WHATSAPP_ENABLED", fleet)
    monkeypatch.setattr(
        env_settings, "OPENAI_API_KEY", "sk-pytest-not-a-real-key" if key else ""
    )
    monkeypatch.setattr(
        site_settings,
        "get_setting",
        lambda k, default=None, **kw: (
            "true" if (k == settings_store.KEY_AI_REPLIES_ENABLED and toggle) else default
        ),
    )
    site_settings.invalidate_cache()


@pytest.fixture
def ai_on(monkeypatch):
    _switches(monkeypatch)


def _thread(db, world, *, window_hours=2.0):
    now = datetime.now(timezone.utc)
    row = WhatsAppConversation(
        account_id=world["engagement_id"],
        product_id=world["product_id"],
        wa_contact_id=uuid.uuid4().hex[:20],
        phone_e164="+2376000" + uuid.uuid4().hex[:5],
        state="open",
        unread_count=1,
        last_inbound_at=now,
        service_window_expires_at=now + timedelta(hours=window_hours),
        locale="fr",
        meta={},
    )
    db.add(row)
    db.flush()
    return row


class Recorder:
    """A stub model that records the prompts it was handed."""

    def __init__(self, text="Nous ouvrons tous les jours, vous etes le bienvenu."):
        self.text = text
        self.calls: list[tuple[str, str]] = []

    def __call__(self, system_prompt: str, user_prompt: str) -> provider.Completion:
        self.calls.append((system_prompt, user_prompt))
        return provider.Completion(
            status=provider.STATUS_OK, text=self.text, model="recorder-stub"
        )

    @property
    def sent(self) -> str:
        return "\n".join(s + "\n" + u for s, u in self.calls)


_RUN = 5


def assert_not_forwarded(prompt: str, value: str, label: str) -> None:
    """No run of ``_RUN`` characters of ``value`` survives into the prompt.

    Equality is not the test: a redactor that leaves "690112233" as
    "6901•••33" has still put most of a Cameroonian mobile number on a
    server in the United States.
    """
    compact = "".join(ch for ch in value if ch.isalnum())
    haystack = "".join(ch for ch in prompt if ch.isalnum())
    assert compact, label
    for start in range(0, max(1, len(compact) - _RUN + 1)):
        window = compact[start : start + _RUN]
        assert window not in haystack, f"{label}: {window!r} reached the model"


# ===========================================================================
# 1. Defect 1 — the customer's message goes to OpenAI in the United States
# ===========================================================================

# Every way a Cameroonian actually types the same MTN MoMo number.
PHONE_FORMATS = (
    "+237690112233",
    "+237 690 11 22 33",
    "+237 6 90 11 22 33",
    "237690112233",
    "00237690112233",
    "690112233",
    "690 11 22 33",
    "690-11-22-33",
    "(+237) 690.11.22.33",
)


@pytest.mark.parametrize("written", PHONE_FORMATS)
def test_a_phone_number_never_reaches_the_model_in_any_format(db, world, ai_on, written):
    """MoMo and Orange Money numbers are phone numbers, in every notation."""
    thread = _thread(db, world)
    model = Recorder()

    respond.draft(
        db,
        thread,
        f"Bonjour, ma commande est en retard, mon numero est {written}",
        model=model,
    )

    assert model.calls, "the model was never called — this test proves nothing"
    assert_not_forwarded(model.sent, "690112233", f"phone as {written!r}")


def test_an_english_message_is_redacted_exactly_like_a_french_one(db, world, ai_on):
    thread = _thread(db, world)
    model = Recorder("We are open every day, you are welcome.")

    respond.draft(
        db,
        thread,
        "Hello, where is my order? My number is +237 677 45 89 12",
        model=model,
    )

    assert model.calls
    assert_not_forwarded(model.sent, "677458912", "english phone")


def test_a_card_number_never_reaches_the_model(db, world, ai_on):
    thread = _thread(db, world)
    model = Recorder()

    respond.draft(
        db,
        thread,
        "Bonjour, ma commande est en retard, ma carte 4111 1111 1111 1111",
        model=model,
    )

    assert model.calls
    assert_not_forwarded(model.sent, "4111111111111111", "card pan")


def test_a_long_bare_identifier_never_reaches_the_model(db, world, ai_on):
    """Nine digits in a row is a phone or an ID card. It is not an order id."""
    thread = _thread(db, world)
    model = Recorder()

    respond.draft(
        db, thread, "Bonjour, ma commande est en retard, mon matricule 109876543", model=model
    )

    assert model.calls
    assert_not_forwarded(model.sent, "109876543", "bare 9-digit identifier")


# The identity-labelled shapes never reach the model at all, because "cni",
# "identite", "passeport" and "documents" are KYC vocabulary and escalate
# before the provider is called. That is defence in depth, not a reason to
# leave the redactor untested — an operator wiring a second entry point, or a
# widening of the safe intents, would remove the escalation and leave this as
# the only rule standing. So the redactor is asserted directly.
IDENTITY_TEXTS = (
    ("Ma CNI est 109876543", "109876543"),
    ("Numero de carte nationale d'identite: AB1234567", "AB1234567"),
    ("My national ID card number is 109876543", "109876543"),
    ("Mon passeport est n° 1234567AB", "1234567AB"),
    ("My passport number is 1234567AB", "1234567AB"),
    ("Mon NIU est P099812345678", "P099812345678"),
)


@pytest.mark.parametrize("text,secret", IDENTITY_TEXTS)
def test_identity_numbers_are_redacted_in_both_languages(text, secret):
    cleaned = pii.redact_customer_text(text)
    assert_not_forwarded(cleaned, secret, f"identity number in {text!r}")


def test_an_email_address_is_redacted():
    cleaned = pii.redact_customer_text("Mon email est marie.ngoh@example.cm merci")
    assert "marie.ngoh@example.cm" not in cleaned
    assert "example.cm" not in cleaned


def test_a_labelled_home_address_is_redacted_in_both_languages():
    fr = pii.redact_customer_text("Bonjour, mon adresse est 12 rue Njo-Njo Bonapriso Douala.")
    en = pii.redact_customer_text("Hi, I live at 12 Njo-Njo street, Bonapriso, Douala.")
    for cleaned in (fr, en):
        assert "Njo-Njo" not in cleaned
        assert "Bonapriso" not in cleaned


# --- and the other half: the layer must still be able to help --------------

REFERENCES_TO_THINGS = (
    ("Bonjour, ou est ma commande 4417 ?", "4417"),
    ("Hello, where is my order 4417?", "4417"),
    ("Bonjour, ma commande est en retard depuis 25 minutes", "25"),
    ("Bonjour, ma commande CMD-4417 est en retard", "CMD-4417"),
)


@pytest.mark.parametrize("text,reference", REFERENCES_TO_THINGS)
def test_a_reference_to_a_thing_survives_so_the_model_can_still_act_on_it(
    db, world, ai_on, text, reference
):
    """Redact identifiers that identify a *person*. Keep references to a *thing*.

    A redactor that turns "my order 12345 is late" into "my order [id] is
    late" has made the layer useless without making anybody safer: an order
    number is not a person, and it is the only handle the model has on the
    question being asked.
    """
    thread = _thread(db, world)
    model = Recorder()

    respond.draft(db, thread, text, model=model)

    assert model.calls
    assert reference in model.sent, f"{reference!r} was masked and the model cannot help"


def test_a_fact_value_carrying_pii_is_masked_before_it_is_sent_abroad(db, world, ai_on):
    """Facts come from our own products, and go to the same third party."""
    thread = _thread(db, world)
    model = Recorder()

    respond.draft(
        db,
        thread,
        "Bonjour, ou est ma commande ?",
        model=model,
        facts=(
            respond.Fact(
                key="customer_phone", value="+237690112233", source="quatafood.orders_api"
            ),
            respond.Fact(key="eta_minutes", value="25", source="quatafood.orders_api"),
        ),
    )

    assert model.calls
    assert_not_forwarded(model.sent, "690112233", "phone inside a fact")
    # …and the fact that is not PII is still there to answer with.
    assert "25" in model.sent


def test_a_secret_keyed_fact_never_reaches_the_model(db, world, ai_on):
    """The shared redactor already knows what a credential key looks like."""
    thread = _thread(db, world)
    model = Recorder()

    respond.draft(
        db,
        thread,
        "Bonjour, ou est ma commande ?",
        model=model,
        facts=(
            respond.Fact(key="otp_code", value="483920", source="quatapay.auth_api"),
        ),
    )

    assert model.calls
    assert "483920" not in model.sent


def test_redaction_happens_before_the_model_not_after(db, world, ai_on):
    """The property that matters: the value never leaves the building.

    A redactor on the *output* would still have sent the customer's ID card
    number to a server in another jurisdiction. This asserts the prompt
    itself is clean, which is the only place the check is worth anything.
    """
    thread = _thread(db, world)
    model = Recorder()

    respond.draft(
        db, thread, "ou est ma commande, mon numero +237690112233", model=model
    )

    system_prompt, user_prompt = model.calls[0]
    assert "690112233" not in system_prompt + user_prompt
    assert "[" in user_prompt, "the redaction left no trace the model can reason about"


# ===========================================================================
# 2. Defect 2 — with no facts, an allow-list of shapes, not a list of words
# ===========================================================================

class Hostile:
    """A model that says exactly what the attacker wants it to say."""

    def __init__(self, text: str):
        self.text = text
        self.calls: list[tuple[str, str]] = []

    def __call__(self, system_prompt: str, user_prompt: str) -> provider.Completion:
        self.calls.append((system_prompt, user_prompt))
        return provider.Completion(
            status=provider.STATUS_OK, text=self.text, model="hostile-stub"
        )


# A safe, answerable question in each language, so the refusal below is the
# output gate firing and not the message itself being unanswerable.
ASK_FR = "bonjour comment ca marche votre service svp"
ASK_EN = "hello how does the app work please"

# Claims that carry no possessive, no digit, and no word from any list. Every
# one of these reached ``ACTION_REPLY`` before the allow-list existed.
UNGROUNDED_FR = (
    # A decision, stated with no possessive at all.
    "Le dossier est en regle, il n y a rien a signaler.",
    "Bonne nouvelle, la demande a bien ete acceptee.",
    # The customer's own words, quoted back as confirmation.
    'Vous avez dit : "ma commande est bien arrivee", et c est exact.',
    # A delivery, in the passive, with nobody's name on it.
    "La livraison a ete effectuee hier soir.",
    # An identity decision with no K, no Y and no C anywhere near it.
    "Tout est en ordre du cote des pieces fournies.",
)

UNGROUNDED_EN = (
    "The file is in order and there is nothing outstanding.",
    "Good news, the request has gone through.",
    'You said "my order arrived", and that is right.',
    "The delivery was completed last night.",
    "Everything you sent us has been looked at and it is fine.",
)


@pytest.mark.parametrize("claim", UNGROUNDED_FR)
def test_a_french_claim_with_no_listed_word_is_refused_when_nothing_was_looked_up(
    db, world, ai_on, claim
):
    thread = _thread(db, world)
    decision = respond.draft(db, thread, ASK_FR, model=Hostile(claim))

    assert decision.action != respond.ACTION_REPLY, (
        f"an ungrounded claim reached the customer: {claim!r}"
    )
    assert decision.text is None


@pytest.mark.parametrize("claim", UNGROUNDED_EN)
def test_an_english_claim_with_no_listed_word_is_refused_when_nothing_was_looked_up(
    db, world, ai_on, claim
):
    thread = _thread(db, world)
    decision = respond.draft(db, thread, ASK_EN, model=Hostile(claim))

    assert decision.action != respond.ACTION_REPLY, (
        f"an ungrounded claim reached the customer: {claim!r}"
    )
    assert decision.text is None


SPELLED_OUT = (
    (ASK_FR, "Il reste douze mille cinq cents unites disponibles."),
    (ASK_EN, "There are twelve thousand five hundred units left."),
)


@pytest.mark.parametrize("ask,claim", SPELLED_OUT)
def test_a_number_spelled_out_in_words_is_still_a_number(db, world, ai_on, ask, claim):
    """Pinned in both languages. "douze mille cinq cents" reads like a fact."""
    thread = _thread(db, world)
    decision = respond.draft(db, thread, ask, model=Hostile(claim))
    assert decision.action != respond.ACTION_REPLY


# --- the controls: refusing everything is not a defence --------------------

PERMITTED = (
    # A general statement about QUATA, which is all this layer ever knew.
    (ASK_FR, "Nous ouvrons tous les jours, vous etes le bienvenu."),
    (ASK_EN, "We are open every day, you are welcome."),
    # A pleasantry and a clarifying question.
    (ASK_FR, "Bonjour ! Comment puis-je vous aider ?"),
    (ASK_EN, "Hello! How can I help you today?"),
    # The honest answer when there is nothing to look it up with.
    (ASK_FR, "Je transmets votre demande a un collegue."),
    (ASK_EN, "I am passing your question to a colleague."),
)


@pytest.mark.parametrize("ask,reply", PERMITTED)
def test_the_safe_shapes_still_go_out(db, world, ai_on, ask, reply):
    """Without this, "refuse everything" would pass every test above."""
    thread = _thread(db, world)
    decision = respond.draft(db, thread, ask, model=Hostile(reply))

    assert decision.action == respond.ACTION_REPLY, f"{reply!r} was refused: {decision.reason}"
    assert decision.text


def test_the_allow_list_is_only_in_force_when_nothing_was_looked_up(db, world, ai_on):
    """The control that makes the seam worth building.

    The same sentence, refused with no facts, is sendable once a product API
    has actually answered — which is the entire point of defect 3.
    """
    thread = _thread(db, world)
    # Deliberately free of the classifier's English markers ("arrive",
    # "minutes"), which would make this a language test instead.
    claim = "Votre commande sera livree dans 25 mn."

    refused = respond.draft(db, thread, ASK_FR, model=Hostile(claim))
    assert refused.action != respond.ACTION_REPLY

    allowed = respond.draft(
        db,
        thread,
        ASK_FR,
        model=Hostile(claim),
        facts=(
            respond.Fact(
                key="eta_minutes", value="25", source="quatafood.orders_api"
            ),
        ),
    )
    assert allowed.action == respond.ACTION_REPLY
    assert allowed.grounded is True


# ===========================================================================
# 3. Defect 3 — the seam, and its null default
# ===========================================================================

def _query(world, *, text="ou est ma commande", intent="order_status"):
    return fact_seam.FactQuery(
        product_slug=world["product_slug"],
        intent=intent,
        language="fr",
        phone_e164="+237600000000",
        text=text,
    )


def test_the_default_implementation_is_null_and_that_is_correct_today(world):
    """No product is connected to QCP, so nothing can be known about anybody."""
    assert fact_seam.source_for("no-such-product") is fact_seam.NULL_SOURCE
    assert fact_seam.lookup(_query(world)) == ()


def test_a_product_can_implement_the_contract_and_supply_facts(world):
    class OrdersApi:
        def fetch(self, query):
            assert query.intent == "order_status"
            return (
                respond.Fact(
                    key="eta_minutes", value="25", source="quatafood.orders_api"
                ),
            )

    fact_seam.register(world["product_slug"], OrdersApi())
    try:
        found = fact_seam.lookup(_query(world))
        assert [f.key for f in found] == ["eta_minutes"]
        assert found[0].source == "quatafood.orders_api"
    finally:
        fact_seam.unregister(world["product_slug"])


def test_a_source_that_explodes_yields_no_facts_rather_than_a_guess(world):
    """A broken integration must degrade to "nothing is known", never to a 500.

    ``handle_inbound`` is called from ingest, and ingest must return 200 to
    Meta or the whole WABA's subscription is disabled.
    """
    class Broken:
        def fetch(self, query):
            raise RuntimeError("upstream down")

    fact_seam.register(world["product_slug"], Broken())
    try:
        assert fact_seam.lookup(_query(world)) == ()
    finally:
        fact_seam.unregister(world["product_slug"])


def test_a_source_cannot_smuggle_a_credential_into_the_prompt(world):
    class Leaky:
        def fetch(self, query):
            return (
                respond.Fact(key="otp_code", value="483920", source="x.api"),
                respond.Fact(key="card_number", value="4111111111111111", source="x.api"),
                respond.Fact(key="eta_minutes", value="25", source="x.api"),
            )

    fact_seam.register(world["product_slug"], Leaky())
    try:
        found = fact_seam.lookup(_query(world))
        blob = " ".join(f"{f.key}={f.value}" for f in found)
        assert "483920" not in blob
        assert "4111111111111111" not in blob
        assert "25" in blob
    finally:
        fact_seam.unregister(world["product_slug"])


def test_the_seam_is_wired_into_the_inbound_turn(db, world, ai_on, monkeypatch):
    """The seam is worthless if the production path still hard-codes ``()``."""
    captured: dict = {}

    class OrdersApi:
        def fetch(self, query):
            captured["query"] = query
            return (
                respond.Fact(
                    key="eta_minutes", value="25", source="quatafood.orders_api"
                ),
            )

    def spy(db_, conversation, text, *, facts=(), **kw):
        captured["facts"] = tuple(facts)
        return respond.Decision(
            action=respond.ACTION_ESCALATE,
            reason="pytest_spy",
            text=None,
            kind="text",
            intent="order_status",
            confidence=0.9,
            language="fr",
            must_escalate=False,
            model="",
            prompt_version=respond.PROMPT_VERSION,
            fact_sources=(),
            grounded=False,
        )

    thread = _thread(db, world)
    account = db.get(WhatsAppAccount, thread.account_id)
    fact_seam.register(world["product_slug"], OrdersApi())
    monkeypatch.setattr(respond, "draft", spy)
    try:
        turn.handle_inbound(
            db,
            account=account,
            conversation=thread,
            product_id=world["product_id"],
            text="bonjour ou est ma commande",
        )
    finally:
        fact_seam.unregister(world["product_slug"])

    assert "facts" in captured, "the turn never reached the engine"
    assert [f.key for f in captured["facts"]] == ["eta_minutes"]
    # And what the product was asked was the redacted text, not the raw one.
    assert captured["query"].product_slug == world["product_slug"]


def test_the_product_is_asked_with_a_redacted_question(db, world, ai_on, monkeypatch):
    captured: dict = {}

    class OrdersApi:
        def fetch(self, query):
            captured["query"] = query
            return ()

    thread = _thread(db, world)
    account = db.get(WhatsAppAccount, thread.account_id)
    fact_seam.register(world["product_slug"], OrdersApi())
    monkeypatch.setattr(provider, "complete", Hostile("Bonjour !"))
    try:
        turn.handle_inbound(
            db,
            account=account,
            conversation=thread,
            product_id=world["product_id"],
            text="bonjour ou est ma commande, mon numero est +237690112233",
        )
    finally:
        fact_seam.unregister(world["product_slug"])

    assert "query" in captured
    assert "690112233" not in captured["query"].text


def test_the_null_seam_is_what_makes_the_no_claims_rule_real(db, world, ai_on):
    """Defect 2 and defect 3 are the same defect.

    With the null implementation — today's shipping state — no product API
    was consulted, so the AI may say nothing about this person's order, and
    the refusal below is that rule firing on the real, unconfigured path.
    """
    thread = _thread(db, world)
    account = db.get(WhatsAppAccount, thread.account_id)

    assert fact_seam.lookup(_query(world)) == ()

    gate = handover.decide(
        db,
        thread,
        signals=handover.Signals(understood=True, confidence=0.95, language="fr"),
        account_purpose=account.purpose,
        product_id=world["product_id"],
        text=ASK_FR,
    )
    assert gate.action == handover.ACT_ANSWER

    decision = respond.draft(
        db, thread, ASK_FR, model=Hostile("Votre commande a bien ete livree hier soir.")
    )
    assert decision.action == respond.ACTION_ESCALATE
    assert decision.text is None
