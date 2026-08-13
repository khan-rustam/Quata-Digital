"""Round 9 — the two shapes of security code round 8's rule still forwarded.

Round 8 taught the redactor to read the *words* around a 4–8 digit run rather
than its length, so ``mon code 483920`` is stripped while ``ma commande 4417``
survives. That rule is right and this module does not relitigate it. It pins
the two openings left in it, both found by probing the shipped redactor rather
than by reading its tests:

1. **A separator nobody enumerated.** Round 8 proved a space, a dot and a
   hyphen no longer defeat the code rule, and re-proved the same for round 7's
   9-digit identifier catch-all. But ``_DIGIT_RUN`` never spanned a **comma**,
   so ``code 483,920`` was two runs of three digits — both under
   ``CODE_MIN_DIGITS`` — and the code went to OpenAI verbatim beside the word
   that named it. The same crack reopened round 7's hole one level up:
   ``109,876,543`` is a nine-digit identifier and was forwarded whole, as was a
   CNI written with comma grouping.

2. **The pasted OTP inside a real sentence.** The lone-number tie-break only
   fires when the customer wrote six words or fewer, so ``483920 ne marche
   pas`` was caught and ``Bonjour, 483920 ne marche pas, aidez moi svp`` was
   not. That second shape is the one customers actually send: they paste the
   code *because* it did not work, and they say so, in a greeting and a
   sentence. Round 8's own long-message case passed only because the
   authentication-context flag was set for it; with no recent auth message —
   a customer who retries an hour later, or whose code came from another
   product — the identical sentence leaked.

   The fix is a tie-break, not a new override: wording that says a number
   *failed* ("ne marche pas", "expire", "j'ai essaye", "invalid", "I tried")
   makes an otherwise unbound number a code. It is consulted only after both
   the code words and the reference words have had their say, so
   ``ma commande 4417 ne marche pas`` still reaches the model with its order
   number intact — which is the whole point of the layer.

Both languages throughout, because a rule tested in one of Cameroon's two is
not tested.

Every test here was observed failing against the round-8 redactor, except the
ones marked **held behaviour**, which were observed passing and are here to
stop the fix eating a reference to a thing.
"""
from __future__ import annotations

import pytest

from app.services.whatsapp.ai import pii


# Six consecutive characters of a six-digit code is the whole code. Compare
# alphanumerics only, so regrouping ("483 920") is not mistaken for redaction.
_RUN = 6


def assert_not_forwarded(prompt: str, value: str, label: str) -> None:
    compact = "".join(ch for ch in value if ch.isalnum())
    haystack = "".join(ch for ch in prompt if ch.isalnum())
    assert compact, label
    for start in range(0, max(1, len(compact) - _RUN + 1)):
        window = compact[start : start + _RUN]
        assert window not in haystack, f"{label}: {window!r} reached the model"


# ===========================================================================
# 1. The comma — the separator round 8 did not enumerate
# ===========================================================================

COMMA_GROUPED_CODES = (
    # French
    "mon code 483,920 ne marche pas",
    "le code de verification 483,920",
    "mon mot de passe est 48,39,20",
    "OTP 483,920 refuse",
    # English
    "the code you sent me was 483,920",
    "my verification code is 483,920",
    "security code: 483,920",
    "my one time password 48,39,20 failed",
)


@pytest.mark.parametrize("text", COMMA_GROUPED_CODES)
def test_a_comma_does_not_defeat_the_code_rule(text):
    """A comma split the run into two 3-digit halves, both below the floor."""
    assert_not_forwarded(pii.redact_customer_text(text), "483920", f"comma {text!r}")


COMMA_GROUPED_IDENTIFIERS = (
    ("109,876,543", "109876543"),
    ("mon numero est 690,11,22,33", "690112233"),
    ("ma cni 109,876,543", "109876543"),
    ("my national ID card number 109,876,543", "109876543"),
    ("mon compte 10005,00001,12345678901,76", "12345678901"),
)


@pytest.mark.parametrize("text,secret", COMMA_GROUPED_IDENTIFIERS)
def test_a_comma_does_not_defeat_the_long_identifier_rule(text, secret):
    """Round 7's hole, one separator over: 9+ digits is never a reference."""
    assert_not_forwarded(pii.redact_customer_text(text), secret, f"comma id {text!r}")


SEPARATORS_ALREADY_CLOSED = (
    ("109876543", "109876543"),
    ("109 876 543", "109876543"),
    ("109.876.543", "109876543"),
    ("109-876-543", "109876543"),
    ("10005 00001 12345678901 76", "12345678901"),
    ("mon code 483 920 ne marche pas", "483920"),
    ("mon code 48.39.20 ne marche pas", "483920"),
    ("the code you sent me was 483-920", "483920"),
)


@pytest.mark.parametrize("text,secret", SEPARATORS_ALREADY_CLOSED)
def test_the_separators_reported_closed_are_actually_closed(text, secret):
    """Held behaviour, re-verified rather than trusted.

    Round 7 reported the one-space hole fixed and it was not. This asserts it
    independently for every separator both earlier rounds claimed, so the
    comma fix cannot be credited for work that was never done.
    """
    assert_not_forwarded(pii.redact_customer_text(text), secret, f"separator {text!r}")


# ===========================================================================
# 2. The pasted OTP that arrives inside a real sentence
# ===========================================================================

CODE_IN_A_REAL_SENTENCE = (
    # French — the customer pastes the code precisely because it failed.
    "Bonjour, 483920 ne marche pas, aidez moi svp",
    "Bonjour monsieur, j'ai essaye 483920 mais ca ne marche pas du tout",
    "bonsoir, 483920 ne fonctionne pas, je n'arrive pas a me connecter",
    "svp aidez moi, 483920 est refuse a chaque fois que j'essaie",
    "bonjour, le 483920 est expire je crois, pouvez vous m'aider",
    # English
    "Hello, I tried 483920 but it says invalid, can you help",
    "483920 is not working, please help me quickly",
    "good morning, 483920 was rejected again and I cannot log in",
    "hi there, I entered 483920 and it is still wrong, what do I do",
    "hello sir, 483920 has expired I think, please send another one",
)


@pytest.mark.parametrize("text", CODE_IN_A_REAL_SENTENCE)
def test_a_pasted_code_in_a_full_sentence_never_leaves_the_country(text):
    """The commonest real shape, and the one the word-count tie-break missed.

    No code word, no recent authentication message — only the customer saying
    the number did not work. That is enough: numbers that fail are codes.
    """
    assert_not_forwarded(pii.redact_customer_text(text), "483920", f"sentence {text!r}")


REFERENCES_IN_THE_SAME_SENTENCES = (
    # A reference word sits before the number, so it wins however the
    # customer complains about it afterwards.
    ("Bonjour, ma commande 4417 ne marche pas, aidez moi svp", "4417"),
    ("Bonjour, ma commande 4417 est en retard depuis hier soir svp", "4417"),
    ("Hello, order 4417 is late, where is my parcel, please help me now", "4417"),
    ("Hello, my order 4417 is wrong and I tried calling you twice", "4417"),
    ("Bonjour, mon colis 88214 est bloque depuis trois jours, aidez moi", "88214"),
    ("Bonjour, ma facture 8891 n'est pas payee, ca ne marche pas", "8891"),
    ("Hello, my invoice 8891 is not paid, the payment does not work", "8891"),
    ("Bonjour, le montant de 25000 fcfa ne marche pas quand je paie", "25000"),
    ("Hello, the price 25000 fcfa does not work when I try to pay", "25000"),
    ("Bonjour, ma reference de suivi 4417 est invalide d'apres le site", "4417"),
)


@pytest.mark.parametrize("text,reference", REFERENCES_IN_THE_SAME_SENTENCES)
def test_the_failure_tie_break_does_not_eat_a_reference(text, reference):
    """Held behaviour. The tie-break must lose to a word that names a thing.

    These are the exact sentences the new rule is most likely to over-read:
    the customer is complaining that something *did not work*, and the thing
    that did not work is an order, a parcel, an invoice or an amount. Strip
    the number here and the model has nothing left to answer with.
    """
    assert reference in pii.redact_customer_text(text), (
        f"{reference!r} was masked and the model can no longer help"
    )


def test_a_code_and_a_reference_still_go_different_ways_in_one_sentence():
    cleaned = pii.redact_customer_text(
        "Bonjour, ma commande 4417 est en retard et en plus 483920 ne marche pas"
    )
    assert "4417" in cleaned, "the order reference was eaten"
    assert_not_forwarded(cleaned, "483920", "code beside an order number")

    cleaned_en = pii.redact_customer_text(
        "Hello, my order 4417 is late and also I tried 483920 and it failed"
    )
    assert "4417" in cleaned_en, "the order reference was eaten (english)"
    assert_not_forwarded(cleaned_en, "483920", "code beside an order number (english)")


# ===========================================================================
# 3. What the comma must not start eating
# ===========================================================================

AMOUNTS_AND_DATES_THAT_MUST_SURVIVE = (
    ("Bonjour, combien coute 12,000 fcfa ?", "12,000"),
    ("Hello, is the total 12,000 XAF correct?", "12,000"),
    ("Bonjour, j'ai paye un montant de 25,000 fcfa hier", "25,000"),
    ("Bonjour, commande du 12/08/2026 a 14h30", "2026"),
    ("Hello, my order from 12/08/2026 at 14h30", "2026"),
)


@pytest.mark.parametrize("text,kept", AMOUNTS_AND_DATES_THAT_MUST_SURVIVE)
def test_widening_the_run_does_not_eat_a_price_or_a_date(text, kept):
    """Held behaviour. A comma is also a thousands separator.

    Spanning it must not turn "12,000 fcfa" into a code — the reference words
    around an amount are what stop that, and they are pinned here so the
    widened run cannot quietly start eating money.
    """
    assert kept in pii.redact_customer_text(text), f"{kept!r} was masked in {text!r}"


def test_a_product_supplied_amount_is_not_read_as_a_code():
    """Held behaviour. A fact is a lookup result, not a customer's guess."""
    assert pii.safe_fact_value("order_total", "12,000 FCFA") == "12,000 FCFA"
    assert pii.safe_fact_value("order_id", "4417") == "4417"


def test_a_credential_keyed_fact_is_still_dropped():
    assert "483920" not in pii.safe_fact_value("otp_code", "483,920")


def test_redaction_is_still_idempotent():
    for text in (
        "mon code 483,920 ne marche pas",
        "Bonjour, 483920 ne marche pas, aidez moi svp",
        "109,876,543",
        "Bonjour, ma commande 4417 ne marche pas",
    ):
        once = pii.redact_customer_text(text)
        assert pii.redact_customer_text(once) == once, f"not idempotent: {text!r}"
