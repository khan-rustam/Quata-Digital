"""Drafting a reply — and the gates that decide it never leaves the building.

``draft()`` returns a **decision**, not a message. It sends nothing, writes
no ``whatsapp_messages`` row and touches no thread state — the one row it
writes is its own audit record; the caller takes the decision to the gateway
(which still enforces routing, the service window and the account purpose on
its own) or to the agent queue. Keeping the two apart is what lets every rule
below be tested without a transport.

Three outcomes, and only one of them produces text:

* ``reply``    — the draft passed every gate. Free-form text, engagement
                 number, inside the service window.
* ``escalate`` — a human takes this thread. Sends nothing.
* ``silent``   — nothing to do and nobody to page: the AI is switched off,
                 a human already owns the thread, the window has closed, or
                 the thread is on the Verify number.

**The model is not a security boundary.** The system prompt below tells the
model what not to say, and that instruction is a *hint*: a customer can talk
it out of any of it, and eventually will. So every rule that matters is a
check in this module, applied on the way in (before the model is asked) and
on the way out (before the draft is allowed to exist), and the model's own
compliance is never relied upon:

* **The Verify number.** ``account.purpose`` is read from storage, never
  taken from the caller, and an authentication account returns ``silent``
  before the provider is called. Not one AI message on that number.
* **OTP shapes.** Any reply mentioning a code, OTP or password is refused
  whatever the digits are, so a "helpful" model repeating a verification
  code produces an escalation instead of a message.
* **Figures.** Every digit run in the draft must appear in a fact a product
  API supplied *in this request*. A model that invents a balance, a total or
  an ETA produces an escalation, because an invented number on this fleet is
  worse than no answer. Facts are the only source: a figure echoed from the
  customer's own message is not evidence either.
* **Money words.** Balance, refund, payment, KYC and friends are refused in
  the output outright. The intents that legitimately need those words all
  escalated on the way in, so this only ever fires on a model that wandered.
* **Language.** The reply must be in the language the customer wrote in.
  Answering a francophone customer in English is a support failure, and
  ``classify`` escalates rather than guessing when it cannot tell.

**The service window.** Free-form is legal only inside Meta's 24 hours. This
checks it so the AI does not queue work the gateway will refuse — it does not
route around that gate, and the gateway remains the enforcement point.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional, Sequence

from sqlalchemy.orm import Session

from app.models import (
    WhatsAppAccount,
    WhatsAppAuditLog,
    WhatsAppConversation,
    WhatsAppMessage,
)

from .. import audit, conversations
from . import classify as classifier
from . import pii, provider


# Bumped whenever the prompt below changes, so an audited reply can be tied
# to the exact instructions that produced it.
PROMPT_VERSION = "qcp-support-2026-08-c"

PURPOSE_ENGAGEMENT = "engagement"
PURPOSE_AUTHENTICATION = "authentication"
KIND_TEXT = "text"

ACTION_REPLY = "reply"
ACTION_ESCALATE = "escalate"
ACTION_SILENT = "silent"


@dataclass(frozen=True)
class Fact:
    """One value a product API returned **in this request**.

    ``source`` names the API that answered, and it is what makes a reply
    traceable: "the ETA came from ``quatafood.orders_api``" is checkable
    afterwards, "the model said 25 minutes" is not.
    """

    key: str
    value: str
    source: str

    def trace(self) -> str:
        return f"{self.key}@{self.source}"


@dataclass(frozen=True)
class Decision:
    action: str
    reason: str
    text: Optional[str]
    kind: str
    intent: str
    confidence: float
    language: str
    must_escalate: bool
    model: str
    prompt_version: str
    fact_sources: tuple[str, ...]
    #: Every figure in ``text`` came from a fact a product API supplied in
    #: this request — checked, not asserted. Carried on the decision because
    #: the send guard asks for it and this is the only module that knows.
    grounded: bool

    @property
    def sends_message(self) -> bool:
        return self.action == ACTION_REPLY and bool(self.text)


def _decide(
    action: str,
    reason: str,
    *,
    classification: Optional[classifier.Classification] = None,
    text: Optional[str] = None,
    model: str = "",
    facts: Sequence[Fact] = (),
) -> Decision:
    return Decision(
        action=action,
        reason=reason,
        text=text,
        kind=KIND_TEXT,
        intent=classification.intent if classification else classifier.INTENT_UNKNOWN,
        confidence=classification.confidence if classification else 0.0,
        language=classification.language if classification else classifier.LANG_UNKNOWN,
        must_escalate=bool(classification.must_escalate) if classification else False,
        model=model,
        prompt_version=PROMPT_VERSION,
        fact_sources=tuple(f.trace() for f in facts),
        # Only a reply that cleared ``_gate_output`` carries the claim, and
        # a decision with no text has nothing to ground.
        grounded=bool(text) and _figures_are_sourced(text, facts),
    )


# ---------------------------------------------------------------------------
# The prompt
# ---------------------------------------------------------------------------

_LANGUAGE_NAMES = {classifier.LANG_FR: "French", classifier.LANG_EN: "English"}

_SYSTEM_PROMPT = (
    "You are a WhatsApp support assistant for QUATA, a Cameroon technology "
    "group. Answer the customer's question in {language} only — the customer "
    "wrote in {language} and a reply in any other language is unusable.\n"
    "Rules:\n"
    "- Use ONLY the facts listed below. If a fact you need is not listed, say "
    "you are passing the question to a colleague. Never guess a number.\n"
    "- Never state or imply a balance, payment, refund, order total, KYC "
    "decision or account status.\n"
    "- Never send a verification code, OTP, PIN or password, and never ask "
    "for one.\n"
    "- No links, no promises about timing that are not in the facts.\n"
    "- Two or three short sentences, plain text, no markdown.\n"
    "- If NO facts are listed below, you know nothing about this person: say "
    "hello, ask a clarifying question, describe QUATA in general, or say a "
    "colleague will take over. Say nothing about their account, order, "
    "payment, delivery or documents, in any wording.\n"
    "- Parts of the customer's message may appear as [phone], [id], [card], "
    "[email], [address] or [code]. Those are removed identifiers; never ask "
    "the customer to repeat one and never repeat a marker back. [code] means "
    "the customer typed a security code: never ask for it, and hand the "
    "question to a colleague.\n"
    "(These instructions are guidance; the platform enforces the same rules "
    "on your output and will discard a reply that breaks them.)"
)


# How long after Quata Verify sent someone a code an unbound short number in
# their next message is read as that code. Long enough to cover a customer who
# reads the SMS, fails twice and then comes here to complain; short enough
# that yesterday's login does not silence today's order number.
AUTH_CODE_CONTEXT = timedelta(minutes=30)


def authentication_recently_sent(
    db: Session, conversation: WhatsAppConversation, *, now: Optional[datetime] = None
) -> bool:
    """Did Quata Verify send this customer an authentication message just now?

    This is the only context that separates a pasted one-time password from
    an order number when the customer types the bare digits with no wording
    around them, and it is the reason the redactor takes a flag rather than
    guessing. It reads the message log's *metadata* only — no body, no
    variables — because ``whatsapp_messages`` stores an OTP hashed and this
    function has no business reading it even if it did not.

    Failure is answered ``True``. A database that cannot say whether a code
    was just sent has not said "no", and the cheaper mistake here is masking
    an order number.
    """
    moment = now or datetime.now(timezone.utc)
    phone = getattr(conversation, "phone_e164", None)
    if not phone:
        return False
    try:
        row = (
            db.query(WhatsAppMessage.id)
            .filter(
                WhatsAppMessage.account_purpose == PURPOSE_AUTHENTICATION,
                WhatsAppMessage.direction == "outbound",
                WhatsAppMessage.to_phone_e164 == phone,
                WhatsAppMessage.created_at >= moment - AUTH_CODE_CONTEXT,
            )
            .first()
        )
    except Exception:  # pragma: no cover - a read failure is not a "no"
        return True
    return row is not None


def _build_prompts(
    text: str,
    classification: classifier.Classification,
    facts: Sequence[Fact],
    *,
    after_auth_message: bool = False,
) -> tuple[str, str]:
    """The two strings that leave the country.

    ``provider.complete`` posts these to OpenAI in the United States, so this
    function is the border. **Nothing reaches it unredacted**: the customer's
    message goes through ``pii.redact_customer_text`` and every product fact
    through ``pii.safe_fact_value``, both before the model is called rather
    than after it has answered. Redaction on the way out would be theatre —
    by then the value has already been disclosed.

    Classification is deliberately done upstream on the *raw* text: it is
    local, deterministic code, and a message whose intent depends on a phone
    number does not exist.
    """
    language = _LANGUAGE_NAMES.get(classification.language, "English")
    system = _SYSTEM_PROMPT.format(language=language)
    fact_lines = "\n".join(
        f"- {f.key}: {pii.safe_fact_value(f.key, f.value)} (source: {f.source})"
        for f in facts
    )
    user = (
        f"Detected intent: {classification.intent}\n"
        f"Facts available (from product APIs, this request only):\n"
        f"{fact_lines or '- none'}\n\n"
        "Customer message:\n"
        f"{pii.redact_customer_text(text, after_auth_message=after_auth_message)[:2000]}"
    )
    return system, user


# ---------------------------------------------------------------------------
# Output gates
# ---------------------------------------------------------------------------

# Anything that reads like a credential the customer is meant to type.
_OTP_SHAPED = re.compile(
    r"\b(otp|code|codes|pin|password|passcode|passwords|"
    r"mot de passe|one[\s-]?time|2fa|token)\b",
    re.IGNORECASE,
)

# The vocabulary of a claim this layer is never allowed to make. Every intent
# that legitimately needs these words escalated before the model was called.
_MONEY_WORDS = re.compile(
    r"\b(balance|solde|refund|refunded|rembours\w*|payment|paiement|paid|"
    r"pay[ée]|charged|invoice|facture|montant|transfer|transfert|virement|"
    r"transaction|wallet|portefeuille|fcfa|xaf|cfa|francs?|argent|fonds|"
    r"versement|d[ée]p[ôo]t|retrait|withdraw\w*|deposit\w*|"
    r"kyc|verified|v[ée]rifi[ée]s?|valid[ée]?e?s?|approuv[ée]s?|approved|"
    r"rejected|refus[ée]s?|"
    r"debited|credited|suspended|suspendu|blocked|bloqu[ée])\b",
    re.IGNORECASE,
)

_DIGIT_RUN = re.compile(r"\d+")

# A quantity spelled out in words is still a quantity. This was a real hole:
# the digit rule below only sees ``\d+``, so "douze mille cinq cents francs"
# — an invented balance a Cameroonian customer cannot tell from a real one —
# passed every gate. Small words ("un", "one", "deux", "two") are deliberately
# absent: "un moment" and "one minute" are not claims about anybody's money,
# and a rule that blocked them would make the layer useless without making it
# safer. What is listed is the vocabulary of an *amount*.
_SPELLED_NUMBER = re.compile(
    r"\b("
    r"cent|cents|mille|milles|million|millions|milliard|milliards|"
    r"vingt|trente|quarante|cinquante|soixante|quatre[\s-]vingts?|"
    r"douze|treize|quatorze|quinze|seize|dix[\s-]?(?:sept|huit|neuf)|"
    r"hundred|thousand|billion|"
    r"twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|"
    r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen"
    r")\b",
    re.IGNORECASE,
)


def _figures_are_sourced(text: str, facts: Sequence[Fact]) -> bool:
    """Every figure in the draft must appear in a supplied fact value.

    Digit runs *and* spelled-out amounts. A model that writes "twelve
    thousand five hundred" has stated a figure exactly as much as one that
    writes "12500", and a customer reads the two the same way.
    """
    corpus = " ".join(str(f.value) for f in facts)
    if any(run not in corpus for run in _DIGIT_RUN.findall(text)):
        return False
    # A spelled-out amount can never be matched against a fact value (which
    # holds "12500", not "douze mille"), so it is permitted only when there
    # is nothing to state: no facts, no amounts, in any notation.
    return not (_SPELLED_NUMBER.search(text) and not facts)


# ---------------------------------------------------------------------------
# What may be said when **nothing was looked up**
#
# This is an allow-list, and the inversion is the whole point. The previous
# rule was "a second-person possessive next to a noun from a list", which is
# a deny-list wearing a structure, and a reviewer beat it twice in an
# afternoon: state the decision with no possessive ("le dossier est en
# regle"), or quote the customer's own sentence back at them as confirmation.
# There is always another phrasing, so a rule that refuses only the phrasings
# somebody thought of will always be one phrasing behind.
#
# So: with zero facts the reply must **match one of four permitted shapes**,
# clause by clause, and anything that matches none of them is refused. Being
# unrecognised is now a refusal rather than a pass, which is what makes the
# rule provable — a new synonym for "approved" does not win, because it was
# never the synonym that was being detected.
#
# The four shapes, each of which is safe with no knowledge of the customer:
#
#   1. a **pleasantry**   — every token is a greeting or a politeness word;
#   2. a **question**     — the AI may ask, as long as it names no domain
#                           entity ("votre dossier est approuve ?" is an
#                           assertion wearing a question mark);
#   3. a **handover**     — "je transmets votre demande a un collegue": the
#                           only shape allowed to name the customer's things,
#                           because it makes no claim about them and it is
#                           the honest answer when nothing was looked up;
#   4. a **general statement about QUATA** — the subject must be QUATA, the
#                           app or the service; it may name no domain entity
#                           and no second person. "Nous ouvrons tous les
#                           jours" survives. "Tout est en ordre" does not,
#                           because its subject is the customer's situation.
#
# Clauses, not sentences: splitting on commas and colons stops a claim riding
# along behind a permitted opener ("Bonjour, votre dossier est approuve").
#
# The residual, stated rather than hidden: a first-person-plural sentence
# that names no entity and no second person ("nous confirmons que tout est
# bon") is permitted and is vague reassurance. It asserts nothing about an
# account, order, payment, delivery or document — which is the rule's stated
# scope — and every intent for which it would be a *decision* escalated
# before the model was called. Narrowing it further means enumerating
# predicates, which is the deny-list this replaced.
# ---------------------------------------------------------------------------

# Domain entities: the things only a product API can truthfully describe.
# Used *positively* here — naming one is what disqualifies a clause from
# shapes 2 and 4 — rather than as a list of words to search for.
_DOMAIN_ENTITY = re.compile(
    r"\b(compte|comptes|commande|commandes|dossier|dossiers|paiement|paiements|"
    r"versement|versements|livraison|livraisons|livre|livree|livrees|argent|"
    r"fonds|facture|factures|document|documents|piece|pieces|justificatif|"
    r"justificatifs|abonnement|colis|remboursement|transfert|virement|"
    r"portefeuille|carte|solde|profil|demande|demandes|identite|cni|niu|"
    r"verification|verifications|statut|statuts|transaction|transactions|"
    r"account|accounts|order|orders|payment|payments|delivery|deliveries|"
    r"balance|refund|file|files|money|funds|invoice|subscription|parcel|"
    r"package|shipment|transfer|wallet|card|identity|profile|status|kyc)\b"
)

_SECOND_PERSON = re.compile(r"\b(vous|votre|vos|tu|ton|ta|tes|toi|you|your|yours)\b")

# Shape 4's subject. QUATA, its app, its service — never the customer and
# never "everything".
#
# Round 7: ``notre``/``nos``/``our`` used to be accepted bare, which made
# "Our answer is positive" — an approval — a statement whose subject the rule
# considered to be QUATA. A possessive is only a QUATA subject when what is
# possessed is QUATA itself, so the head noun is now required and listed,
# exactly as it already was for ``l application`` and ``the app``.
_GENERIC_SUBJECT = re.compile(
    r"^(?:nous|on|quata|we|"
    r"(?:notre|nos|our)\s+(?:equipe|equipes|application|app|service|services|"
    r"site|plateforme|boutique|magasin|entreprise|societe|"
    r"team|platform|store|shop|company|business)|"
    r"l\s*(?:application|app|equipe)|le\s+(?:service|site|magasin)|"
    r"la\s+(?:plateforme|boutique)|"
    r"the\s+(?:app|application|service|site|platform|team|store|shop))\b"
)

# Openers that may precede shape 4's subject without changing it.
_OPENER = re.compile(
    r"^(?:et|and|mais|but|donc|so|alors|puis|then|oui|yes|non|no|ok|"
    r"bonjour|bonsoir|salut|hello|hi|hey|merci|thanks|thank\s+you|"
    r"bien\s+sur|of\s+course|en\s+fait|actually)\b[\s,]*"
)

# Shape 3. Subject, verb and target all pinned: it is the *act of handing
# over* that earns the exemption from the entity rule, not the word
# "collegue" appearing somewhere in a sentence.
#
# Round 7 note: this used to be enough on its own, and it was a free pass for
# the rest of the clause. ``search`` finds the handover *somewhere*, and the
# old code then returned True for the whole clause — so a claim did not have
# to beat the rule, it only had to share a clause with a handover, which one
# "et" achieves: "je passe le dossier a un collegue **et tout est en regle de
# votre cote**" and "I am passing this to a colleague **and your order has
# been delivered to you**" both went out. So the match now has to account for
# the whole clause: what precedes it may only be an opener, and what follows
# it may only be the ordinary reassurance about the human who is coming.
_HANDOVER = re.compile(
    r"\b(je|j|nous|i|we)\b[^\n]{0,60}?"
    r"\b(transmets|transmettons|transfere|transferons|passe|passons|oriente|"
    r"orientons|contacte|contactons|demande|demandons|invite|mets|"
    r"pass|passing|hand|handing|forward|forwarding|transfer|transferring|"
    r"escalate|escalating|connect|connecting|ask|asking|check|checking)\b"
    r"[^\n]{0,60}?"
    r"\b(collegue|collegues|conseiller|conseillere|agent|agents|humain|"
    r"equipe|colleague|colleagues|teammate|human|team|advisor|specialist)\b"
)

# Shape 1. Every token must be in here, so a claim cannot hide inside a
# greeting: "bonjour votre solde est bon" is not a pleasantry.
#
# ``oui``/``yes``/``non``/``no``/``ok``/``d accord`` were removed in round 7.
# A bare affirmation is not a pleasantry — it is an unqualified answer to
# whatever the customer last asked, and "elle est arrivee alors ?" → "oui" is
# a delivery this layer never looked up. They remain in ``_OPENER``, so
# "Oui, nous ouvrons tous les jours" and "Ok, je transmets a un collegue"
# are unaffected; only a clause that is *nothing but* the affirmation is
# refused.
_PLEASANTRY_TOKENS = frozenset(
    """
    bonjour bonsoir salut coucou hello hi hey good morning evening afternoon
    day night merci thanks thank welcome bienvenu bienvenue bienvenus
    de rien desole desolee sorry apologies
    excusez moi je vous en prie nous sommes suis etes est are is am the le la
    les a to tres very much beaucoup bonne journee soiree have nice great
    ravi enchante pleasure you and et
    """.split()
)

# What a handover clause may end with, and nothing else. An allow-list like
# every other rule here: a token that is not in it refuses the clause, so
# appending a claim to a handover fails without anybody having to have
# thought of that particular claim.
_HANDOVER_TAIL_TOKENS = frozenset(
    """
    et and qui who which va vont will going to pour for
    repondre repondra repondront reply replies respond answer
    reviendra reviendront revenir get back come contact contacter
    contactera contacteront contacted vous you te toi
    rapidement vite bientot soon shortly quickly right away as possible
    tout de suite instant moment maintenant now peu sous des que
    merci thanks thank s il plait plait svp please d accord ok
    """.split()
)

# A completed action, in either language. With **nothing looked up** the AI
# knows of no action that has been taken on this customer's behalf, so a
# clause in the perfect describes an event it invented — "nous avons recu la
# somme" (a payment), "nous avons donne une suite favorable" (an approval),
# "on a deja tout traite", "we have received the sum".
#
# Round 6 permitted all of these, because shape 4 constrained the *subject*
# and nothing constrained the predicate, and declared the residual harmless on
# the grounds that it "asserts nothing about an account, order, payment,
# delivery or document". A payment and an approval are exactly that.
#
# The auxiliary is required to follow the subject pronoun directly, which is
# what keeps this a rule about grammatical aspect rather than a word list:
# bare "a" is the French preposition far more often than it is the auxiliary
# ("nous ouvrons a huit heures"), and only "on a", "nous avons", "we have"
# and their kin are evidence of a completed action. It costs one legitimate
# shape — "nous avons une application mobile" — which is sayable as "notre
# application est …", and refusing is the safe direction.
# "deja" / "already" is included because it is the same assertion by a
# different route: it says the event is behind us, whatever tense carries it.
# "Nous encaissons deja" and "Nous expedions deja" read to a customer as "we
# have already taken your money / already shipped your parcel", and nothing
# was looked up.
_COMPLETED_ACTION = re.compile(
    r"\b(?:deja|already)\b|"
    r"\b(?:nous|on|je|j|quata|we|i|it)\s+(?:n\s+|ne\s+|not\s+)?"
    r"(?:a|ai|as|avons|avez|ont|avait|avaient|"
    r"have|has|had|was|were|did|got)\b"
)

# An embedded complement — "nous confirmons QUE tout est en ordre", "we can
# confirm THAT everything is fine". Vouching for a proposition is a claim
# about the proposition, and with nothing looked up there is no proposition
# the AI is in a position to vouch for. This closes the residual round 6
# named and left open.
_EMBEDDED_CLAIM = re.compile(r"\b(que|qu|that)\b")

# A determiner-headed noun phrase — "une issue favorable", "le reglement",
# "au necessaire", "the settlement", "a position". This is what separates a
# statement *about QUATA* from a statement about **this customer's matter**
# wearing QUATA as its subject, and it is the second half of the shape-4
# hole: banning the perfect ("nous avons enregistre le reglement") left the
# present ("nous enregistrons le reglement") untouched, and "nous confirmons
# une issue favorable" is an approval whichever tense it is in.
#
# The distinction is grammatical, not lexical, which is what stops the next
# synonym winning: a general statement about the business predicates over no
# determinate object ("nous ouvrons tous les jours", "we deliver all over
# town", "we are open every day"), while a claim about the customer's case
# has to name the case. The exceptions are the generic time expressions that
# are adverbials rather than objects, and they are listed rather than
# guessed.
#
# It costs the descriptive shape the system prompt invites — "nous sommes une
# entreprise camerounaise" is refused because of "une entreprise" — and the
# consequence of that refusal is an escalation to a human, which is the safe
# direction and the reason it is acceptable.
_GENERIC_TIME_NOUNS = frozenset(
    """
    jour jours journee journees semaine semaines mois annee annees an ans
    temps moment moments heure heures matin matins soir soirs midi minuit
    day days week weeks month months year years time times moment moments
    morning evening afternoon night clock hour hours
    """.split()
)

_DETERMINED_NOUN = re.compile(
    r"\b(?:le|la|les|l|un|une|des|du|au|aux|ce|cet|cette|ces|"
    r"notre|nos|mon|ma|mes|son|sa|ses|leur|leurs|"
    r"the|a|an|this|that|these|those|our|my|his|her|its|their)\s+([a-z]+)"
)

# The same object, pronominalised. "Our team is handling **it** right now"
# names no noun and still asserts that work is under way on this customer's
# matter — which nothing looked up. Caught separately because a pronoun has
# no determiner for the rule above to see.
_PRONOUN_OBJECT = re.compile(r"\b(it|them|ca|cela|ceci)\b")

# An affirmation reported rather than uttered — "nous sommes en mesure de
# dire **oui**", "we can say **yes**". It carries the same decision as the
# bare "oui" that shape 1 no longer accepts, so it is refused in the same
# place a bare affirmation is.
_ASSENT = re.compile(r"\b(oui|yes|yep|yeah|non|no|nope|favorable|favourable)\b")

_CLAUSE = re.compile(r"[^.,;:!?\n]+[.,;:!?\n]?")
_TOKEN = re.compile(r"[a-z0-9]+")
_COMBINING = re.compile(r"[̀-ͯ]")


def _fold(text: str) -> str:
    """Lowercase, accents removed. "identité" and "identite" are one word."""
    decomposed = unicodedata.normalize("NFD", str(text or "").lower())
    return _COMBINING.sub("", decomposed)


def _strip_openers(body: str) -> str:
    """Drop leading "et", "bonjour", "en fait" … until none is left."""
    while True:
        stripped = _OPENER.sub("", body, count=1)
        if stripped == body:
            return body
        body = stripped


def _is_whole_clause_handover(folded: str) -> bool:
    """Shape 3, judged over the **whole** clause rather than a substring.

    The handover itself may be preceded only by openers and pleasantries, and
    followed only by ``_HANDOVER_TAIL_TOKENS`` — "qui vous repondra bientot"
    and nothing with any content of its own. Everything else the model
    appended is a separate claim and is judged on its own merits, which for a
    claim about this customer means refused.
    """
    match = _HANDOVER.search(folded)
    if match is None:
        return False
    head = _strip_openers(folded[: match.start()].strip())
    if any(token not in _PLEASANTRY_TOKENS for token in _TOKEN.findall(head)):
        return False
    tail = folded[match.end() :]
    return all(token in _HANDOVER_TAIL_TOKENS for token in _TOKEN.findall(tail))


def _clause_is_permitted(clause: str) -> bool:
    """Does this clause match one of the four shapes safe with zero facts?"""
    folded = _fold(clause)
    tokens = _TOKEN.findall(folded)
    if not tokens:
        return True  # punctuation or whitespace: nothing is being claimed

    # 1 ─ a pleasantry, and nothing but.
    if all(token in _PLEASANTRY_TOKENS for token in tokens):
        return True

    # 3 ─ handing the question to a human. Checked before the entity rule:
    #     naming the thing being handed over is the point of the sentence.
    if _is_whole_clause_handover(folded):
        return True

    # 2 ─ a question that names nothing of the customer's.
    if clause.rstrip().endswith("?"):
        return not _DOMAIN_ENTITY.search(folded)

    # 4 ─ a general statement about QUATA. Present tense, about QUATA itself,
    #     naming none of the customer's things, vouching for nothing, and
    #     predicating over no determinate object.
    body = _strip_openers(folded.strip())
    subject = _GENERIC_SUBJECT.match(body)
    if subject is None:
        return False
    if (
        _DOMAIN_ENTITY.search(folded)
        or _SECOND_PERSON.search(folded)
        or _COMPLETED_ACTION.search(folded)
        or _EMBEDDED_CLAIM.search(folded)
        or _PRONOUN_OBJECT.search(folded)
        or _ASSENT.search(folded)
    ):
        return False
    # Scanned after the subject, so the subject's own determiner ("l
    # application", "le service") is not mistaken for an object.
    return all(
        noun in _GENERIC_TIME_NOUNS
        for noun in _DETERMINED_NOUN.findall(body[subject.end() :])
    )


# "et" and "and" conjoin two predicates, so they start a new clause even
# without punctuation. Without this, one conjunction laundered a second
# subject through the first one's permission: "nous ouvrons tous les jours
# **et il reste de quoi**" was judged as a single clause whose subject is
# QUATA. Splitting here means the conjoined half is judged on its own, which
# for a claim about the customer means refused.
_CONJUNCTION = re.compile(r"\b(?:et|and)\b")


def _clauses(text: str) -> list[str]:
    parts = []
    for chunk in _CLAUSE.findall(text or ""):
        parts.extend(_CONJUNCTION.split(chunk))
    return parts


def _permitted_with_no_facts(text: str) -> bool:
    """Every clause must match a permitted shape. One failure refuses the draft."""
    return all(_clause_is_permitted(clause) for clause in _clauses(text))


def _gate_output(
    text: str, classification: classifier.Classification, facts: Sequence[Fact]
) -> Optional[str]:
    """The reason this draft may not be sent, or None if it may."""
    body = (text or "").strip()
    if not body:
        return "empty_output"
    if len(body) > provider.MAX_REPLY_CHARS:
        return "output_too_long"
    if _OTP_SHAPED.search(body):
        return "otp_shaped_output"
    if _MONEY_WORDS.search(body):
        return "money_claim_in_output"
    if not _figures_are_sourced(body, facts):
        return "unverified_figure"
    if classifier.detect_language(body) != classification.language:
        return "language_mismatch"
    # The structural rule, and the important one — checked last so that a
    # draft which is *also* in the wrong language is reported as the language
    # failure it is. Everything above is a word list, and a word list is a
    # game the attacker wins eventually. This one does not ask what words
    # were used: with **no product API consulted in this request** the AI
    # knows nothing about this person, so the reply is confined to the four
    # shapes above — a pleasantry, a question, a handover, or a statement
    # about QUATA itself. Anything else, in any wording, in either language,
    # is refused.
    if not facts and not _permitted_with_no_facts(body):
        return "ungrounded_claim_about_the_customer"
    return None


# ---------------------------------------------------------------------------
# The decision
# ---------------------------------------------------------------------------

def draft(
    db: Session,
    conversation: WhatsAppConversation,
    text: str,
    *,
    facts: Sequence[Fact] = (),
    model: Optional[Callable[[str, str], provider.Completion]] = None,
    now=None,
    assisting_agent: bool = False,
) -> Decision:
    """Decide what to do about one inbound customer message, and record why.

    ``model`` is the completion callable — ``provider.complete`` in
    production, a stub in tests. Injecting it is what lets every gate be
    asserted without a key, a network or a bill.

    The audit row is written **here** rather than by the caller. "Every AI
    reply is audited" cannot rest on an integrator remembering to call a
    second function, and the one case where a row would be noise rather than
    evidence — the switch is off, so there was no decision to explain — is
    skipped explicitly. Like ``routing._deny``, this writes and flushes on
    the caller's session and never commits.

    ``assisting_agent`` is set by ``suggest_reply`` and by nothing else. It
    relaxes exactly one gate — "a human already owns this thread" — because
    that is the *precondition* of drafting for an agent, not a reason to stay
    quiet: the console refuses to draft for a thread the caller has not
    claimed. Nothing else moves. The Verify number, the escalation
    categories, the output gates and the service window are unchanged, and
    the decision it produces still cannot send anything on its own.
    """
    decision = _resolve(
        db,
        conversation,
        text,
        facts=facts,
        model=model,
        now=now,
        assisting_agent=assisting_agent,
    )
    if not (decision.action == ACTION_SILENT and decision.reason == "ai_disabled"):
        audit_decision(db, conversation, decision)
    return decision


def _resolve(
    db: Session,
    conversation: WhatsAppConversation,
    text: str,
    *,
    facts: Sequence[Fact],
    model: Optional[Callable[[str, str], provider.Completion]],
    now,
    assisting_agent: bool = False,
) -> Decision:
    """The decision itself. Reads state, calls the model, writes nothing."""
    call = model or provider.complete

    # 1 ─ the kill switch. Stops the machine; the human queue is untouched.
    #     Not consulted when drafting *for* an agent: that path has its own
    #     switch (``whatsapp.ai_suggestions_enabled``, checked by the console
    #     before it gets here), sends nothing, and puts a human between the
    #     model and the customer. Two risks, two switches, both default off.
    if not assisting_agent and not provider.ai_replies_enabled():
        return _decide(ACTION_SILENT, "ai_disabled")

    classification = classifier.classify(text)

    # 2 ─ a human already owns this thread. The AI does not talk over them —
    #     unless it is drafting for that very human, which is the one case
    #     where their ownership is the reason to draft rather than not to.
    if conversation.assignee_id is not None and not assisting_agent:
        return _decide(ACTION_SILENT, "human_assigned", classification=classification)

    # 3 ─ money, KYC, fraud, complaints, legal, distress, injection attempts
    #     and anything written in a language this cannot read. Checked before
    #     the window and before the number, because escalation sends nothing
    #     and a fraud report must reach a human even at 3am on a closed thread.
    if classification.must_escalate:
        return _decide(
            ACTION_ESCALATE,
            classification.escalation_reason or "must_escalate",
            classification=classification,
        )

    # 4 ─ the Verify number. Read from the account row, never from the caller.
    account = db.get(WhatsAppAccount, conversation.account_id)
    if account is None or account.purpose != PURPOSE_ENGAGEMENT:
        return _decide(ACTION_SILENT, "auth_account", classification=classification)

    # 5 ─ free-form is legal only inside Meta's 24 hours.
    if not conversations.service_window_open(conversation, now=now):
        return _decide(ACTION_SILENT, "outside_service_window", classification=classification)

    # 6 ─ only the intents that are safe to answer at all.
    if not classification.is_safe:
        return _decide(ACTION_ESCALATE, "unknown_intent", classification=classification)

    # 7 ─ the model. No key is the shipping state, not an error.
    system_prompt, user_prompt = _build_prompts(
        text,
        classification,
        facts,
        after_auth_message=authentication_recently_sent(db, conversation, now=now),
    )
    completion = call(system_prompt, user_prompt)
    if completion.status == provider.STATUS_NOT_CONFIGURED:
        return _decide(
            ACTION_ESCALATE, "provider_not_configured", classification=classification
        )
    if not completion.ok:
        return _decide(
            ACTION_ESCALATE,
            "provider_error",
            classification=classification,
            model=completion.model,
        )

    # 8 ─ the output gates. The model has now said something; this is where
    #     it stops mattering what it was told.
    refusal = _gate_output(completion.text, classification, facts)
    if refusal:
        return _decide(
            ACTION_ESCALATE, refusal, classification=classification, model=completion.model
        )

    # 9 ─ belt and braces: re-assert the two properties a reply rests on,
    #     from the same stored state, immediately before returning text.
    if account.purpose != PURPOSE_ENGAGEMENT or not (
        assisting_agent or provider.ai_replies_enabled()
    ):
        return _decide(ACTION_SILENT, "auth_account", classification=classification)

    return _decide(
        ACTION_REPLY,
        "safe_intent_answered_from_facts",
        classification=classification,
        text=completion.text.strip(),
        model=completion.model,
        facts=facts,
    )


# ---------------------------------------------------------------------------
# The agent console's entry point
# ---------------------------------------------------------------------------

def _latest_inbound(messages: Sequence[object]) -> str:
    """The customer's most recent words, out of a page of thread history.

    ``conversations.history`` returns newest first, but the console may hand
    this list back in either order after paging, so the newest inbound row is
    picked by ``id`` rather than by position. Only *inbound* rows count: the
    thing being answered is what the customer said, never what the bot or a
    colleague said, and reading an outbound row here is how an assistant ends
    up answering itself.
    """
    best = None
    for message in messages or ():
        if getattr(message, "direction", None) != "inbound":
            continue
        if best is None or (getattr(message, "id", 0) or 0) > (getattr(best, "id", 0) or 0):
            best = message
    return str(getattr(best, "body", "") or "") if best is not None else ""


def suggest_reply(db: Session, conversation: WhatsAppConversation, *, messages) -> Decision:
    """Draft a reply for a human agent to edit and send. Sends nothing.

    The one name this package publishes on the QCP facade, and the contract
    ``routes_admin_agent`` documents. It returns the ``Decision`` unchanged —
    the console reads ``text`` / ``model`` / ``prompt_version`` / ``action``
    off it — rather than a second shape that could drift from this one.

    **No facts are passed, and that is not an omission.** Nothing in the agent
    console calls QuataPay, QuataFood, Abaqwa or QuataTrade, so no balance,
    total, refund or KYC decision has been fetched in this request. With an
    empty fact list ``_gate_output`` refuses every draft containing a digit
    run, which is the correct answer: a figure in such a draft was invented,
    and the console re-checks the same property independently before it shows
    an agent anything.
    """
    return draft(
        db,
        conversation,
        _latest_inbound(messages),
        facts=(),
        assisting_agent=True,
    )


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------

def audit_decision(
    db: Session, conversation: WhatsAppConversation, decision: Decision
) -> WhatsAppAuditLog:
    """Record why the AI answered — or why it did not.

    The customer's words and the reply body are **not** stored. This table is
    read by operators looking at other people's private support threads; the
    message itself is already in ``whatsapp_messages`` where the thread's own
    access rules apply. What is stored is a digest of the reply, which is
    enough to prove which text a given audit row refers to.
    """
    outcome = audit.OUTCOME_OK if decision.action == ACTION_REPLY else audit.OUTCOME_DENIED
    return audit.record(
        db,
        action=f"ai.{decision.action}",
        resource_type="whatsapp_conversation",
        resource_id=str(conversation.id),
        outcome=outcome,
        reason=decision.reason,
        product_id=conversation.product_id,
        account_id=conversation.account_id,
        details={
            "action": decision.action,
            "reason": decision.reason,
            "intent": decision.intent,
            "confidence": round(float(decision.confidence), 2),
            "language": decision.language,
            "must_escalate": decision.must_escalate,
            "model": decision.model,
            "prompt_version": decision.prompt_version,
            "fact_sources": list(decision.fact_sources),
            "reply_digest": (
                "sha256:" + hashlib.sha256(decision.text.encode("utf-8")).hexdigest()[:8]
                if decision.text
                else None
            ),
        },
    )
