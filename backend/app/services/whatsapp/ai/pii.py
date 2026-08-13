"""What the model is allowed to see of the customer's own words.

Every prompt QCP builds leaves Cameroon. ``provider.complete`` posts it to
OpenAI in the United States, and until this module existed it posted the
customer's message **verbatim** — so a customer who typed their CNI number,
their MoMo number, their card number or their home address had all of it
forwarded to a third party in another jurisdiction. Redaction here happens on
the way **in**, before the model is called. A redactor on the way out would
be theatre: by then the value has already left the building.

**This is not a third redactor.** ``notifications/redaction.py`` owns the
key-based rules (``is_secret_key``, ``is_maskable_key``, ``mask_identifier``,
``redact``) and ``whatsapp/redaction.py`` extends them for template
variables. Both work on *structures* — a dict whose keys name what the values
are. A WhatsApp message is a sentence: there are no keys, so those rules have
nothing to key on. This module is the free-text half, and it delegates every
structured decision back to them (see ``safe_fact_value``), so there is still
one deny-list of credential names in this codebase and not two.

One deliberate difference from ``mask_identifier``. That function keeps a
head and a tail (``12••••••••3456``) because a stored row has to stay
recognisable to a support engineer who is entitled to see it. A prompt
crossing a border has no such reader, so free text is replaced with a *typed
marker* and no digits at all survive.

---------------------------------------------------------------------------
What is redacted, what is kept, and why
---------------------------------------------------------------------------

The line is **a person versus a thing**. An identifier that identifies a
human being is removed; a reference that identifies an object — an order, an
invoice, a parcel — is kept, because it is the only handle the model has on
the question it is being asked. A layer that turns "my order 12345 is late"
into "my order [id] is late" is safe and useless.

REDACTED — identifies a person:

* **Phone numbers**, in every notation a Cameroonian actually types:
  ``+237690112233``, ``+237 690 11 22 33``, ``237 6 90 11 22 33``,
  ``00237...``, the bare local ``690112233``, dotted, dashed, parenthesised.
  MTN MoMo and Orange Money numbers *are* phone numbers, so the same rule
  covers a mobile-money account. Nothing downstream can dial a number, so
  nothing is lost by removing it.
* **Card PANs** — 13–19 digits that pass Luhn. Never any reason to forward
  one, in any jurisdiction.
* **Identity document numbers** — CNI, carte nationale d'identité, NIU,
  passport, "national ID card number". Matched by their *label*, in French
  and English, so an alphanumeric CNI is caught as well as a numeric one.
  The label itself is kept: "ma CNI [id]" still tells the model what the
  customer is talking about.
* **Any bare run of 9 or more digits with no separators.** In Cameroon a
  9-digit run is a phone number or an ID card; no product reference on this
  fleet is that long. This is the rule that catches the shapes nobody
  enumerated.
* **Email addresses**, and a **home address that the customer labelled as
  one** ("mon adresse est …", "I live at …"). Address detection is otherwise
  refused on purpose — see the limits below.

* **A security code the customer typed.** A one-time password is six digits
  and an order number is four, so *length cannot tell them apart* — the rule
  is about the words around the number, not its size. A 4–8 digit run is a
  secret when code/OTP/PIN/*mot de passe*/*vérification* wording sits next to
  it, when the message is essentially nothing but the number, or when we sent
  that customer an authentication message minutes earlier
  (``after_auth_message``). A run bound to *commande*/order/``#``/*facture*
  wording stays. Where the two are genuinely ambiguous the number goes: a
  lost order reference costs one clarifying question, and a leaked OTP costs
  an account — this fleet's codes arrive over WhatsApp and QuataFood login
  has no email fallback behind them.

KEPT — identifies a thing:

* **Digit runs of 8 or fewer that name a thing** — order numbers, invoice
  numbers, tracking references, table numbers, quantities, prices, times,
  dates. These are the handle on the customer's actual question, and they
  survive unless the code rule above claims them.
* **Alphanumeric references** — ``CMD-4417``, ``INV-2024-88``. A reference
  with a product prefix is a thing, not a person.
* **Everything else the customer wrote**, including their name. See below.

Known limits, stated rather than hidden:

* **Names are not redacted.** "Bonjour, je suis Marie Ngoh" is PII and there
  is no reliable way to find a Cameroonian personal name with a regex —
  Cameroonian surnames collide with ordinary French and English words, and a
  name list would either miss most names or eat half of every sentence. The
  honest mitigations are elsewhere: the audit row already stores no message
  text, and a deployment that cannot accept a first name reaching a US
  provider should not enable this feature at all.
* **Unlabelled addresses are not redacted.** "je suis au quartier Bonapriso"
  has no shape to key on, and a heuristic broad enough to catch it eats the
  question. Only the labelled form is removed.
* **A 9-digit order number would be redacted.** No product on this fleet
  issues one; if one ever does, this rule is where it is fixed.
* **A 4–8 digit reference sent with no words at all is redacted** — a bare
  "4417" reads exactly like a bare OTP, and the tie is broken towards the
  secret on purpose. The customer is asked to say what it refers to; nothing
  is lost but one turn.
* **A code written adjacent to another number with only spaces or dots
  between them is not seen as a code.** ``_DIGIT_RUN`` is greedy, so
  "commande 4417. 483920" is one eleven-digit run and matches neither the
  4–8 code rule nor the 9+ identifier rule. Separating them is what a word
  does — "commande 4417 code 483920" is handled — and no observed customer
  writes two unrelated numbers with nothing but a full stop between them.
  Stated so it is a known gap rather than an assumed one.
* **A number spelled out in words is not redacted.** "mon numero six neuf
  zero un un deux deux trois trois" reaches the model intact. Every rule here
  keys on digits, and a word-to-digit parser for two languages is a larger
  thing than the risk justifies — nobody types their MoMo number in words.
  Stated so it is a known gap rather than an assumed one.
* **A bare date and time written with spaces and no punctuation** —
  "12 08 2026 14 30" — is masked as an identifier, because it is twelve
  digits in three or more groups. Written the way people actually write it
  ("12/08/2026 a 14h30") the separators end the run and nothing is touched.

None of this touches storage. ``whatsapp_messages`` still holds what the
customer actually wrote, under the thread's own access rules — this module
only governs the copy that leaves the country.
"""
from __future__ import annotations

import re

from ..redaction import (
    REDACTED,
    is_maskable_key,
    is_secret_key,
    mask_identifier,
    redact,
)


# Typed markers. They carry the *category* so the model can still reason
# about the sentence ("the customer gave a phone number") without holding
# the value. They contain no digits, so the figure gates in ``respond`` do
# not see a number where a redaction happened.
MARK_PHONE = "[phone]"
MARK_CARD = "[card]"
MARK_ID = "[id]"
MARK_EMAIL = "[email]"
MARK_ADDRESS = "[address]"
MARK_CODE = "[code]"

# A run of this many digits with no separators is not a product reference.
BARE_IDENTIFIER_DIGITS = 9

# The size of a security code a human is asked to retype. Four is the
# shortest PIN this fleet issues; eight is the longest code, and also where
# ``BARE_IDENTIFIER_DIGITS`` takes over.
CODE_MIN_DIGITS = 4
CODE_MAX_DIGITS = 8

# How far either side of the number the binding word may sit. Long enough for
# "the code you sent me was 483920", short enough that a word from the
# previous sentence does not bind a number in this one.
CODE_CONTEXT_BEFORE = 48
CODE_CONTEXT_AFTER = 32

# How few other words a message may carry before it counts as "the customer
# sent us a number and little else" — the shape of a pasted OTP.
CODE_LONE_MAX_WORDS = 6


_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

# An address the customer *labelled*. Bounded to the rest of the clause so it
# cannot swallow the question that follows it.
_LABELLED_ADDRESS = re.compile(
    r"(?i)\b("
    r"mon\s+adresse(?:\s+(?:est|c\s?est))?|"
    r"j\s?[’']?\s?habite(?:\s+[àa])?|"
    r"my\s+(?:home\s+)?address\s+is|"
    r"i\s+live\s+(?:at|in)"
    r")\s*[:,]?\s*([^.;\n]{3,80})"
)

# An identity document number, found by its label rather than by its shape —
# a CNI may be numeric or alphanumeric, and the shape alone is not evidence.
_ID_LABEL = re.compile(
    r"(?i)\b("
    r"num[ée]ro\s+(?:de\s+)?(?:la\s+)?(?:c\.?n\.?i\.?|carte(?:\s+nationale)?"
    r"(?:\s+d\s?[’']?\s?identit[ée])?|pi[èe]ce(?:\s+d\s?[’']?\s?identit[ée])?|"
    r"identit[ée]|passeport|passport)|"
    r"carte(?:\s+nationale)?\s+d\s?[’']?\s?identit[ée]|"
    r"national\s+id(?:entity)?(?:\s+card)?(?:\s+(?:number|no))?|"
    r"identity\s+card(?:\s+(?:number|no))?|id\s+card(?:\s+(?:number|no))?|"
    r"id\s+number|c\.n\.i\.?|\bcni\b|\bniu\b|\bnui\b|passeport|passport"
    r")"
    r"(?:\s*(?:n[°ºo]\.?|num[ée]ro|number|no\.?|est|is|:|=|#|,)\s*)*"
    r"\s*([A-Za-z0-9][A-Za-z0-9\-/]{3,19})"
)

# One run of digits, however the human grouped it. Start and end on a digit,
# so trailing punctuation is never swallowed. The comma is in the class for
# the same reason the space is: without it ``code 483,920`` was two runs of
# three digits, both under ``CODE_MIN_DIGITS``, and ``109,876,543`` was three
# runs of three — so a comma defeated both the code rule and the nine-digit
# catch-all exactly the way a space once did.
_DIGIT_RUN = re.compile(r"\+?\d[\d\s.,\-()]*\d")

_NON_DIGIT = re.compile(r"\D")
_CAMEROON_LOCAL = re.compile(r"[62]\d{8}")

# The words that make a short number a credential. Both languages, because a
# rule tested in one of Cameroon's two languages is not tested.
_CODE_WORD = re.compile(
    r"(?i)\b(?:otp|pin|code|codes|passcode|passcodes|password|passwords|"
    r"token|jeton|2fa|mfa|sms|"
    r"mot\s+de\s+passe|one[\s-]?time(?:\s+(?:password|code|pin))?|"
    r"v[ée]rification|verification|confirmation|authentification|"
    r"authentication|s[ée]curit[ée]|security)\b"
)

# …and the words that make it a handle on a *thing*. A number bound to one of
# these is the question the customer is asking, and removing it leaves the
# model with nothing to answer.
_REFERENCE_WORD = re.compile(
    r"(?i)(?:#|\b(?:commandes?|orders?|facturation|factures?|invoices?|"
    # "recu" is absent on purpose: in French "j'ai recu 483920" is *received*,
    # not *receipt*, and it is exactly how someone reports the code they were
    # sent. The English "receipt" has no such twin.
    r"receipts?|tickets?|colis|parcels?|packages?|livraisons?|"
    r"deliver(?:y|ies)|suivi|tracking|track|r[ée]f[ée]rences?|references?|ref|"
    r"dossiers?|tables?|chambres?|rooms?|"
    r"prix|price|montant|total|combien|co[uû]te|cost|"
    r"fcfa|xaf|cfa|francs?|"
    r"minutes?|heures?|jours?|dates?)\b)"
)

# The weakest of the three signals: the customer saying the number *failed*.
# Order numbers are late, wrong or missing; they are not refused, invalid or
# expired, and nobody "tries" one. This is what catches the commonest real
# shape of a leaked code — a customer pastes the OTP precisely because it did
# not work, and says so in a full sentence, which is more words than the
# lone-number tie-break allows. It never outranks a word that names a thing at
# the same distance; see ``_binding_word``.
_CODE_FAILURE = re.compile(
    r"(?i)(?:"
    r"\bne\s+(?:marche|fonctionne)\s+pas\b|\b(?:marche|fonctionne)\s+pas\b|"
    r"\brefus\w*|\binvalid\w*|\bexpir\w*|\bessay\w*|\bessai\w*|\brejet\w*|"
    r"\bincorrect\w*|"
    r"\b(?:does|did)\s+not\s+work\b|\b(?:doesn|didn)\s?[’']?\s?t\s+work\b|"
    r"\bnot\s+working\b|\brejected\b|\brefused\b|\bwrong\b|\btried\b|"
    r"\bentered\b|\bfailed\b"
    r")"
)

# A word for the purposes of "did the customer send anything but a number?".
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)

# Where one thought ends and the next begins. A word on the far side of this
# is not talking about this number: "ou est ma livraison ? j'ai essaye 483920"
# is a delivery question *and* a code, and the code must not inherit the
# delivery's wording. A comma is deliberately not a boundary — "ma commande
# est en retard, commande #4417" is one thought — and neither is a colon,
# which is how a code is usually introduced ("security code: 483920").
_CLAUSE_END = re.compile(r"[.?!;\n]")


def _binding_word(text: str, start: int, end: int) -> str | None:
    """Whether the words touching this number call it a code or a reference.

    **Nearest wins**, on either side, measured as the gap in characters
    between the word and the number. The decision is taken per number and not
    once per message, which is the only way "ou est ma commande 4417 ? le code
    483920" sends its two numbers different ways.

    Distance rather than side, because the side rule leaked: in "ma commande
    4417 est en retard et en plus 483920 ne marche pas" the word *commande*
    is thirty characters behind the code and still claimed it as a reference,
    forwarding an OTP. A word touching the number outranks one a clause away.

    Ties go code, then reference, then failure wording — so "ma commande 4417
    ne marche pas" is a late order and not a broken code, both words being
    equally close.
    """
    before = text[max(0, start - CODE_CONTEXT_BEFORE) : start]
    boundaries = list(_CLAUSE_END.finditer(before))
    if boundaries:
        before = before[boundaries[-1].end() :]

    after = text[end : end + CODE_CONTEXT_AFTER]
    boundary = _CLAUSE_END.search(after)
    if boundary:
        after = after[: boundary.start()]

    def nearest(pattern: re.Pattern[str]) -> int | None:
        gaps = [len(before) - m.end() for m in pattern.finditer(before)]
        gaps += [m.start() for m in pattern.finditer(after)]
        return min(gaps, default=None)

    winner: str | None = None
    best: int | None = None
    for kind, gap in (
        ("code", nearest(_CODE_WORD)),
        ("reference", nearest(_REFERENCE_WORD)),
        ("code", nearest(_CODE_FAILURE)),
    ):
        if gap is not None and (best is None or gap < best):
            winner, best = kind, gap
    return winner


def _is_lone_number(text: str, start: int, end: int) -> bool:
    """The customer sent us a number and hardly anything else.

    That is the shape of a pasted one-time password: a code arrives, the
    customer copies it into the support thread, sometimes with "ça ne marche
    pas" after it. It is also, unavoidably, the shape of an order number typed
    on its own — see the tie-break in the module docstring.
    """
    rest = text[:start] + " " + text[end:]
    if any(ch.isdigit() for ch in rest):
        return False
    return len(_WORD.findall(rest)) <= CODE_LONE_MAX_WORDS


def _is_code(
    text: str, start: int, end: int, *, after_auth_message: bool, allow_lone: bool
) -> bool:
    """Is this short run of digits a security code rather than a reference?"""
    digits = _NON_DIGIT.sub("", text[start:end])
    if not (CODE_MIN_DIGITS <= len(digits) <= CODE_MAX_DIGITS):
        return False

    binding = _binding_word(text, start, end)
    if binding == "reference":
        return False
    if binding == "code":
        return True
    # Nothing bound it. We know a code reached this customer minutes ago, so
    # an unbound number in their next message is one.
    if after_auth_message:
        return True
    return allow_lone and _is_lone_number(text, start, end)


def _luhn(digits: str) -> bool:
    total = 0
    for index, char in enumerate(reversed(digits)):
        value = ord(char) - 48
        if index % 2:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def _classify_run(raw: str) -> str | None:
    """Which marker this run of digits deserves, or None to leave it alone."""
    digits = _NON_DIGIT.sub("", raw)
    if not digits:
        return None

    # A Cameroonian number, with or without the country code, however typed.
    national = digits[2:] if digits.startswith("00") else digits
    if national.startswith("237") and len(national) == 12:
        national = national[3:]
    if _CAMEROON_LOCAL.fullmatch(national):
        return MARK_PHONE

    # Some other country's number: only when the customer wrote the ``+``,
    # because a bare 11-digit run is not evidence of a dialling code.
    if raw.lstrip().startswith("+") and 10 <= len(digits) <= 15:
        return MARK_PHONE

    if 13 <= len(digits) <= 19 and _luhn(digits):
        return MARK_CARD

    # The catch-all. It used to require ``raw.strip().isdigit()`` — no
    # separators at all — and that made **one space** the whole attack:
    # ``109876543`` was removed and ``109 876 543`` was forwarded verbatim,
    # as was a CEMAC bank RIB (``10005 00001 12345678901 76``), which is
    # printed in exactly that grouping and identifies a person's money.
    #
    # The reason for the old restriction was real, though: ``_DIGIT_RUN`` is
    # greedy across spaces, so "commande 4417 12345" is one run of nine
    # digits and is two references to two *things*. So the rule is now about
    # how the run is grouped, which is what distinguishes one identifier a
    # human wrote out from two short references that happen to be adjacent:
    #
    #   * one group, no separators  — an identifier;
    #   * three or more groups, none of them a lone digit — an identifier
    #     written the way a bank or an ID card prints it;
    #   * two groups totalling twelve or more digits — too long to be two
    #     order numbers.
    #
    # Two short groups ("4417 12345") therefore still survive, which is the
    # documented case. The cost is a bare date-and-time written with spaces
    # and no punctuation ("12 08 2026 14 30") being masked; written the way
    # people actually write it ("12/08/2026 a 14h30") the separators end the
    # run and nothing is touched.
    if len(digits) >= BARE_IDENTIFIER_DIGITS:
        groups = [g for g in _NON_DIGIT.split(raw) if g]
        if (
            len(groups) == 1
            or (len(groups) >= 3 and min(len(g) for g in groups) >= 2)
            or (len(groups) == 2 and len(digits) >= 12)
        ):
            return MARK_ID

    return None


def _redact(text: str, *, after_auth_message: bool, allow_lone_code: bool) -> str:
    value = str(text or "")
    if not value:
        return value

    value = _EMAIL.sub(MARK_EMAIL, value)
    value = _LABELLED_ADDRESS.sub(lambda m: f"{m.group(1)} {MARK_ADDRESS}", value)
    value = _ID_LABEL.sub(lambda m: f"{m.group(1)} {MARK_ID}", value)

    def _replace(match: re.Match[str]) -> str:
        marker = _classify_run(match.group(0))
        if marker:
            return marker
        if _is_code(
            match.string,
            match.start(),
            match.end(),
            after_auth_message=after_auth_message,
            allow_lone=allow_lone_code,
        ):
            return MARK_CODE
        return match.group(0)

    return _DIGIT_RUN.sub(_replace, value)


def redact_customer_text(text: str, *, after_auth_message: bool = False) -> str:
    """Strip personal identifiers out of a customer message.

    Call this on everything that is about to be handed to the model or to a
    product's fact source. It is idempotent — the markers it writes contain
    no digits and match none of the rules — so a value that passes through
    twice is not damaged.

    ``after_auth_message`` is the one piece of context this module cannot
    work out for itself: whether Quata Verify sent this customer an
    authentication message in the last few minutes. When it did, a short
    number the customer types next is a code unless the words around it name
    a thing. ``respond.authentication_recently_sent`` computes it; the
    default is the safe reading for callers that have no conversation in
    hand, because the wording and lone-number rules still apply.
    """
    return _redact(text, after_auth_message=after_auth_message, allow_lone_code=True)


def safe_fact_value(key: str, value: object) -> str:
    """One product-supplied fact value, made safe to send to the model.

    Facts come from our own products and go to the same third party as the
    customer's message, so an order fact carrying the customer's phone number
    is the identical disclosure. The *key* rules are the shared redactor's,
    unchanged and not reimplemented here:

    * a credential-shaped key (``otp_code``, ``api_key``, …) is dropped —
      ``is_secret_key``;
    * an account-shaped key (``card_number``, ``national_id``, …) keeps a
      recognisable head and tail — ``is_maskable_key`` + ``mask_identifier``,
      which is the house style for an identifier a product deliberately
      supplied;
    * everything else is bounded and control-stripped by ``redact`` and then
      swept for free-text identifiers the key never announced.

    The one free-text rule that does **not** apply here is the lone-number
    guess. A fact is a lookup result, not a customer's utterance: a product
    that answers ``order_id: 4417`` has said what the number is, so reading
    it as a possible OTP would erase the only fact the reply could be
    grounded in. The wording rule still applies — a value that says "code
    483920" is a credential whatever its key claims — as does
    ``is_secret_key``, which is what actually catches a code-shaped fact.
    """
    if is_secret_key(str(key)):
        return REDACTED
    cleaned = redact(value)
    text = cleaned if isinstance(cleaned, str) else str(cleaned)
    if is_maskable_key(str(key)):
        return mask_identifier(text)
    return _redact(text, after_auth_message=False, allow_lone_code=False)
