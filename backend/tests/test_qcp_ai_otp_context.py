"""Round 8 — the security code the customer typed, and the order number they typed.

The redactor added in round 6 keeps every digit run of eight or fewer so the
model can still act on "commande 4417". A one-time password is six digits.
So a customer who pastes the login code we just sent them — which they do
constantly, usually while asking why it did not work — had that code posted to
OpenAI in the United States. This fleet sends real OTPs over WhatsApp and
QuataFood login has no email fallback, so that code is an account.

Length alone cannot separate the two: ``483920`` and ``4417`` are the same
shape. **Context** can, and that is what these tests pin:

* a 4–8 digit run next to code/OTP/PIN/*mot de passe*/*vérification* wording
  is a secret, in French and in English;
* a run next to *commande*/order/``#``/*facture* wording is a reference to a
  thing and must survive, or the layer can no longer help anybody;
* a bare number sent on its own, and any unbound run sent just after we sent
  that customer an authentication message, is treated as a secret — a lost
  order reference costs one clarifying question, a leaked OTP costs an account.

Also re-verified here rather than trusted: round 7 reported the "one space
defeats the catch-all" hole fixed (``109876543`` stripped, ``109 876 543``
forwarded). This module asserts that independently, and asserts the same
separator hole does not exist for the new code rule — ``mon code 483 920`` and
``mon code 48 39 20`` must go the same way as ``mon code 483920``.

Every test in this file was observed failing against the round-7 redactor
before ``MARK_CODE`` existed, except the ones explicitly marked as held
behaviour (the reference-survives and grouped-identifier cases), which were
observed passing and are here to stop the new rule eating them.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.db.session import SessionLocal
from app.models import (
    WhatsAppAccount,
    WhatsAppConversation,
    WhatsAppMessage,
    WhatsAppProduct,
    WhatsAppTemplate,
)
from app.services.whatsapp import settings_store
from app.services.whatsapp.ai import pii, provider, respond


SUFFIX = uuid.uuid4().hex[:8]


# ---------------------------------------------------------------------------
# World — both numbers inactive, like every neighbouring QCP suite, so this
# module cannot collide on ``uq_whatsapp_accounts_active_purpose``. Nothing
# here reaches a network.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def world(app_instance):
    from fastapi.testclient import TestClient

    from app.services.whatsapp.credentials import encrypt_wa_secret

    with TestClient(app_instance):
        with SessionLocal() as db:
            token = encrypt_wa_secret(f"PYTEST_NOT_A_REAL_TOKEN_{SUFFIX}")
            engagement = WhatsAppAccount(
                slug=f"otp-quata-{SUFFIX}",
                name="QUATA (otp)",
                purpose="engagement",
                phone_number_id=f"PN-OTP-ENG-{SUFFIX}",
                waba_id=f"WABA-OTP-ENG-{SUFFIX}",
                display_phone="+237600007741",
                api_version="v21.0",
                access_token_encrypted=token,
                is_active=False,
                health="unknown",
            )
            verify = WhatsAppAccount(
                slug=f"otp-verify-{SUFFIX}",
                name="Quata Verify (otp)",
                purpose="authentication",
                phone_number_id=f"PN-OTP-AUTH-{SUFFIX}",
                waba_id=f"WABA-OTP-AUTH-{SUFFIX}",
                display_phone="+237600007742",
                api_version="v21.0",
                access_token_encrypted=token,
                is_active=False,
                health="unknown",
            )
            product = WhatsAppProduct(
                slug=f"otp-food-{SUFFIX}",
                name="OTP Food",
                is_enabled=True,
                api_key_hash="8" * 64,
                api_key_prefix="qcp_otp_test",
                allowed_purposes=["engagement", "authentication"],
                default_locale="fr",
            )
            db.add_all([engagement, verify, product])
            db.flush()
            otp_template = WhatsAppTemplate(
                account_id=verify.id,
                account_purpose="authentication",
                product_id=product.id,
                name=f"otp_login_{SUFFIX}",
                language="fr",
                category="authentication",
                intent="login_otp",
                status="approved",
                variables=["code"],
            )
            db.add(otp_template)
            db.commit()
            ids = {
                "engagement_id": engagement.id,
                "verify_id": verify.id,
                "product_id": product.id,
                "product_slug": product.slug,
                "otp_template_id": otp_template.id,
            }
    yield ids


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session
        session.rollback()


@pytest.fixture
def ai_on(monkeypatch):
    from app.core.config import settings as env_settings
    from app.services import site_settings

    monkeypatch.setenv(settings_store.ENV_AI_REPLIES, "true")
    monkeypatch.setattr(env_settings, "WHATSAPP_ENABLED", True)
    monkeypatch.setattr(env_settings, "OPENAI_API_KEY", "sk-pytest-not-a-real-key")
    monkeypatch.setattr(
        site_settings,
        "get_setting",
        lambda k, default=None, **kw: (
            "true" if k == settings_store.KEY_AI_REPLIES_ENABLED else default
        ),
    )
    site_settings.invalidate_cache()


def _thread(db, world):
    now = datetime.now(timezone.utc)
    row = WhatsAppConversation(
        account_id=world["engagement_id"],
        product_id=world["product_id"],
        wa_contact_id=uuid.uuid4().hex[:20],
        phone_e164="+2376000" + uuid.uuid4().hex[:5],
        state="open",
        unread_count=1,
        last_inbound_at=now,
        service_window_expires_at=now + timedelta(hours=2),
        locale="fr",
        meta={},
    )
    db.add(row)
    db.flush()
    return row


def _auth_message_sent_to(db, world, thread, *, minutes_ago=1.0):
    """Record that Quata Verify sent this customer an authentication message.

    The stored body carries no code — ``whatsapp_messages`` already persists
    OTPs hashed — so this row is *only* the fact that a code was sent, which
    is exactly the signal the redactor is allowed to use.
    """
    sent_at = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    row = WhatsAppMessage(
        message_uid=f"otpmsg-{uuid.uuid4().hex[:20]}",
        account_id=world["verify_id"],
        account_purpose="authentication",
        product_id=world["product_id"],
        template_id=world["otp_template_id"],
        direction="outbound",
        kind="template",
        intent="login_otp",
        to_phone_e164=thread.phone_e164,
        body=None,
        variables={"code": "sha256:deadbeef"},
        status="sent",
        sent_at=sent_at,
        created_at=sent_at,
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
    """No run of ``_RUN`` characters of ``value`` survives into ``prompt``.

    Equality is not the test: half of a six-digit OTP is still most of a
    six-digit OTP, and grouping is not redaction.
    """
    compact = "".join(ch for ch in value if ch.isalnum())
    haystack = "".join(ch for ch in prompt if ch.isalnum())
    assert compact, label
    for start in range(0, max(1, len(compact) - _RUN + 1)):
        window = compact[start : start + _RUN]
        assert window not in haystack, f"{label}: {window!r} reached the model"


# ===========================================================================
# 1. A code the customer typed, found by the words around it — FR and EN
# ===========================================================================

CODE_TEXTS = (
    # French
    ("mon code 483920 ne marche pas", "483920"),
    ("le code 483920 que vous avez envoye ne marche pas", "483920"),
    ("bonjour, mon code de verification est 483920", "483920"),
    ("bonjour, mon code de vérification est 483920", "483920"),
    ("j'ai recu le code 483920 mais rien ne se passe", "483920"),
    # "j'ai recu" is *received*, not *receipt* — the false friend that made an
    # earlier draft of this rule read the commonest OTP report as an invoice.
    ("j'ai recu 483920 par sms", "483920"),
    ("j'ai reçu 483920 par sms", "483920"),
    ("le sms avec 483920", "483920"),
    ("mon mot de passe est 483920", "483920"),
    ("le code secret 4839 ne fonctionne pas", "4839"),
    ("mon PIN 4839 est refuse", "4839"),
    ("code d'authentification : 483920", "483920"),
    ("483920 est le code que vous m'avez envoye", "483920"),
    # English
    ("the code you sent me was 483920", "483920"),
    ("my code 483920 does not work", "483920"),
    ("hello, my verification code is 483920", "483920"),
    ("my one time password is 483920", "483920"),
    ("the OTP 483920 was refused", "483920"),
    ("my PIN 4839 is not accepted", "4839"),
    ("security code: 483920", "483920"),
    ("483920 is the code you sent me", "483920"),
)


@pytest.mark.parametrize("text,secret", CODE_TEXTS)
def test_a_code_next_to_code_wording_never_leaves_the_country(text, secret):
    cleaned = pii.redact_customer_text(text)
    assert_not_forwarded(cleaned, secret, f"code in {text!r}")
    assert pii.MARK_CODE in cleaned, f"{text!r} lost the code without saying so"


# The separator hole again, this time for the rule being added. A space is
# what defeated the 9-digit catch-all in round 7; it must not defeat this one.
GROUPED_CODES = (
    "mon code 483 920 ne marche pas",
    "mon code 48 39 20 ne marche pas",
    "mon code 4 8 3 9 2 0 ne marche pas",
    "mon code 483-920 ne marche pas",
    "mon code 48.39.20 ne marche pas",
    "the code you sent me was 483 920",
    "the code you sent me was 48-39-20",
)


@pytest.mark.parametrize("text", GROUPED_CODES)
def test_grouping_a_code_does_not_defeat_the_code_rule(text):
    assert_not_forwarded(pii.redact_customer_text(text), "483920", f"grouped {text!r}")


# ===========================================================================
# 2. The other half — a reference to a thing must still reach the model
# ===========================================================================

REFERENCES_THAT_MUST_SURVIVE = (
    ("Bonjour, ou est ma commande 4417 ?", "4417"),
    ("Hello, where is my order 4417?", "4417"),
    ("Bonjour, ma commande est en retard, commande #4417", "4417"),
    ("Bonjour, ma commande CMD-4417 est en retard", "CMD-4417"),
    ("Bonjour, ma facture de 2500 FCFA", "2500"),
    ("Hello, my invoice 2500 is wrong", "2500"),
    ("Bonjour, mon colis 88214 n'est pas arrive", "88214"),
    ("Hello, my parcel 88214 has not arrived", "88214"),
    ("Bonjour, commande du 12/08/2026", "2026"),
    ("Bonjour, mes commandes 4417 et 12345", "12345"),
    ("Bonjour, vous ouvrez a 08:00 ?", "08:00"),
    ("Bonjour, ma commande est en retard depuis 25 minutes", "25"),
    ("Bonjour, ma reference de suivi est 4417 merci", "4417"),
    ("Hello, my receipt 4417 is wrong", "4417"),
    ("Bonjour, mon recu de commande 4417", "4417"),
)


@pytest.mark.parametrize("text,reference", REFERENCES_THAT_MUST_SURVIVE)
def test_a_reference_to_a_thing_is_not_eaten_by_the_code_rule(text, reference):
    """Held behaviour. Strip these and the AI can no longer help with an order."""
    assert reference in pii.redact_customer_text(text), (
        f"{reference!r} was masked and the model can no longer help"
    )


def test_a_code_and_an_order_number_in_one_sentence_go_different_ways():
    """The decision is per number, not per message — the hard case, both ways."""
    cleaned = pii.redact_customer_text(
        "Bonjour, ou est ma commande 4417 ? le code 483920 que vous avez envoye "
        "ne marche pas"
    )
    assert "4417" in cleaned, "the order reference was eaten"
    assert_not_forwarded(cleaned, "483920", "code beside an order number")

    cleaned_en = pii.redact_customer_text(
        "Hello, where is my order 4417? the code you sent me was 483920 and it failed"
    )
    assert "4417" in cleaned_en, "the order reference was eaten (english)"
    assert_not_forwarded(cleaned_en, "483920", "code beside an order number (english)")


# ===========================================================================
# 3. The ambiguous middle — a bare number with nothing around it
# ===========================================================================

BARE_CODES = (
    "483920",
    "  483920  ",
    "Bonjour 483920",
    "483920 merci",
    "483920 ne marche pas",
    "483920 does not work",
    "hello 483920",
)


@pytest.mark.parametrize("text", BARE_CODES)
def test_a_bare_number_with_no_context_is_treated_as_a_secret(text):
    """Genuinely ambiguous, so the cheaper mistake is made deliberately.

    A lost order reference costs one clarifying question. A leaked OTP costs
    an account, and this fleet's OTPs arrive on WhatsApp with no email
    fallback behind them.
    """
    assert_not_forwarded(pii.redact_customer_text(text), "483920", f"bare {text!r}")


def test_a_bare_number_after_an_authentication_message_is_a_secret(db, world):
    """The strongest signal available: we sent this customer a code minutes ago."""
    thread = _thread(db, world)
    _auth_message_sent_to(db, world, thread)

    assert respond.authentication_recently_sent(db, thread) is True

    cleaned = pii.redact_customer_text(
        "bonjour je vous ecris parce que 483920 ne fonctionne toujours pas "
        "apres plusieurs essais ce matin",
        after_auth_message=True,
    )
    assert_not_forwarded(cleaned, "483920", "code after an authentication message")


def test_an_old_authentication_message_is_not_context(db, world):
    """Yesterday's login is not why they are typing a number today."""
    thread = _thread(db, world)
    _auth_message_sent_to(db, world, thread, minutes_ago=60 * 26)

    assert respond.authentication_recently_sent(db, thread) is False


def test_no_authentication_message_means_no_authentication_context(db, world):
    thread = _thread(db, world)
    assert respond.authentication_recently_sent(db, thread) is False


def test_the_authentication_context_still_does_not_eat_an_order_number():
    """Even inside the window, wording that names a *thing* wins."""
    cleaned = pii.redact_customer_text(
        "Bonjour, ou est ma commande 4417 ?", after_auth_message=True
    )
    assert "4417" in cleaned
    cleaned_en = pii.redact_customer_text(
        "Hello, where is my order 4417?", after_auth_message=True
    )
    assert "4417" in cleaned_en


# ===========================================================================
# 4. End to end — what actually crosses the border
# ===========================================================================

def test_a_code_in_a_real_support_question_never_reaches_the_model(db, world, ai_on):
    """French. The order number reaches OpenAI; the login code does not."""
    thread = _thread(db, world)
    model = Recorder()

    respond.draft(
        db,
        thread,
        "Bonjour, ou est ma commande 4417 ? le code 483920 que vous avez envoye "
        "ne marche pas",
        model=model,
    )

    assert model.calls, "the model was never called — this test proves nothing"
    assert_not_forwarded(model.sent, "483920", "otp in a french support question")
    assert "4417" in model.sent, "the order reference was masked and the AI is useless"


def test_an_english_code_is_redacted_exactly_like_a_french_one(db, world, ai_on):
    thread = _thread(db, world)
    model = Recorder("We are open every day, you are welcome.")

    respond.draft(
        db,
        thread,
        "Hello, where is my order 4417? the code you sent me was 483920 and it failed",
        model=model,
    )

    assert model.calls
    assert_not_forwarded(model.sent, "483920", "otp in an english support question")
    assert "4417" in model.sent


AMBIGUOUS = (
    "Bonjour, ou est ma livraison ? j'ai essaye 483920 plusieurs fois ce matin"
)


def test_after_an_authentication_message_the_engine_uses_that_context(db, world, ai_on):
    """The same sentence, with and without a code having just been sent.

    Unbound and on its own it is ambiguous enough to keep — it may be a
    reference the customer half-explained. Unbound *minutes after Quata
    Verify sent this person a code*, it is the code.
    """
    quiet = _thread(db, world)
    quiet_model = Recorder()
    respond.draft(db, quiet, AMBIGUOUS, model=quiet_model)
    assert quiet_model.calls
    assert "483920" in quiet_model.sent, (
        "the control is wrong: this number is already masked without the "
        "authentication context, so the test below proves nothing"
    )

    recent = _thread(db, world)
    _auth_message_sent_to(db, world, recent)
    model = Recorder()

    respond.draft(db, recent, AMBIGUOUS, model=model)

    assert model.calls
    assert_not_forwarded(model.sent, "483920", "otp after an authentication message")


def test_the_product_is_asked_without_the_code_either(db, world, ai_on, monkeypatch):
    """The fact seam is a second reader of the same sentence, not an exception.

    A source wired to answer order questions must not be handed the login
    code as its search string — that is a second copy of the credential in a
    second system, which is the disclosure this module exists to prevent.
    """
    from app.models import WhatsAppAccount
    from app.services.whatsapp.ai import facts as fact_seam
    from app.services.whatsapp.ai import turn

    captured: dict = {}

    class OrdersApi:
        def fetch(self, query):
            captured["query"] = query
            return ()

    thread = _thread(db, world)
    account = db.get(WhatsAppAccount, thread.account_id)
    fact_seam.register(world["product_slug"], OrdersApi())
    monkeypatch.setattr(provider, "complete", Recorder("Bonjour !"))
    try:
        turn.handle_inbound(
            db,
            account=account,
            conversation=thread,
            product_id=world["product_id"],
            text="bonjour ou est ma commande 4417, le code 483920 ne marche pas",
        )
    finally:
        fact_seam.unregister(world["product_slug"])

    assert "query" in captured, "the product was never asked — this proves nothing"
    assert_not_forwarded(captured["query"].text, "483920", "otp in the fact query")
    assert "4417" in captured["query"].text, "the product cannot find the order"


def test_the_prompt_tells_the_model_what_the_new_marker_means(db, world, ai_on):
    """A marker the model has never been told about invites it to ask for the value."""
    thread = _thread(db, world)
    model = Recorder()

    respond.draft(db, thread, "Bonjour, ou est ma commande 4417 ?", model=model)

    assert model.calls
    system_prompt = model.calls[0][0]
    assert pii.MARK_CODE in system_prompt


# ===========================================================================
# 5. Round 7's reported fixes, verified here rather than believed
# ===========================================================================

GROUPED_IDENTIFIERS = (
    ("mon matricule 109876543", "109876543"),
    ("mon matricule 109 876 543", "109876543"),
    ("mon matricule 109-876-543", "109876543"),
    ("mon RIB est 10005 00001 12345678901 76", "10005000011234567890176"),
    ("my account number is 10005 00001 12345678901 76", "10005000011234567890176"),
    ("mon numero est 690 11 22 33", "690112233"),
    ("mon numero est +237 690 11 22 33", "690112233"),
    ("ma carte 4111 1111 1111 1111", "4111111111111111"),
)


@pytest.mark.parametrize("text,secret", GROUPED_IDENTIFIERS)
def test_a_separator_still_does_not_defeat_the_long_identifier_rules(text, secret):
    assert_not_forwarded(pii.redact_customer_text(text), secret, f"grouped {text!r}")


# ===========================================================================
# 6. The fact seam must not be damaged by a rule written for free text
# ===========================================================================

FACT_VALUES_THAT_MUST_SURVIVE = (
    ("order_id", "4417"),
    ("order_reference", "88214"),
    ("eta_minutes", "25"),
    ("total_fcfa", "2500"),
)


@pytest.mark.parametrize("key,value", FACT_VALUES_THAT_MUST_SURVIVE)
def test_a_product_supplied_reference_is_not_mistaken_for_a_code(key, value):
    """A fact is a lookup result, not a customer's utterance.

    ``safe_fact_value`` still owns the credential-key rules; what it must not
    acquire is the free-text guess that a lone number is an OTP, because a
    product that answers ``order_id: 4417`` would have its answer erased and
    the reply would be grounded in nothing.
    """
    assert value in pii.safe_fact_value(key, value)


def test_a_credential_keyed_fact_is_still_dropped_whatever_the_new_rule_does():
    """Held behaviour, re-asserted because this file touches the same function."""
    assert "483920" not in pii.safe_fact_value("otp_code", "483920")


def test_redaction_is_still_idempotent():
    once = pii.redact_customer_text("mon code 483920 et ma commande 4417")
    twice = pii.redact_customer_text(once)
    assert once == twice
