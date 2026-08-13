"""What does this customer want, and is it a thing a machine may answer?

Deterministic, keyword-driven, and deliberately **not** a model call. Two
reasons, and the second is the important one:

1. it runs before the provider, so an unconfigured or broken provider still
   produces a usable "send this to a human" answer;
2. the escalation flag is a *control*. A model asked "is this about money?"
   can be talked out of its answer by the same message it is classifying —
   that is what prompt injection is — so the flag that decides whether a
   customer's money question reaches a human is computed from the text by
   code that cannot be argued with.

``classify()`` accepts a ``model_intent`` so a future refinement pass can
propose an intent for a message the keywords did not recognise. It may only
ever *narrow to a safe intent*: it cannot clear a flag, and it cannot
override an intent the rules did recognise. Anything else would make the
model a security boundary.

**Language.** Cameroon is francophone and anglophone, and QCP's customers
write in both — plus Camfranglais and pidgin, which are neither. An
unrecognised language escalates: a support answer in the wrong language is a
worse failure than a slightly slower human, and "guess and hope" on a number
that also carries money traffic is not a support strategy.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


LANG_FR = "fr"
LANG_EN = "en"
LANG_UNKNOWN = "unknown"

# Safe to draft for.
INTENT_OPENING_HOURS = "opening_hours"
INTENT_HOW_IT_WORKS = "how_it_works"
INTENT_ORDER_STATUS = "order_status"
INTENT_GREETING = "greeting"

# Never drafted for — a human takes these.
INTENT_MONEY = "money"
INTENT_KYC = "kyc"
INTENT_FRAUD = "fraud"
INTENT_COMPLAINT = "complaint"
INTENT_LEGAL = "legal"
INTENT_DISTRESS = "distress"
INTENT_AUTH = "auth"
INTENT_INJECTION = "injection"

INTENT_UNKNOWN = "unknown"

SAFE_INTENTS = frozenset(
    {INTENT_OPENING_HOURS, INTENT_HOW_IT_WORKS, INTENT_ORDER_STATUS, INTENT_GREETING}
)
ESCALATE_INTENTS = frozenset(
    {
        INTENT_MONEY,
        INTENT_KYC,
        INTENT_FRAUD,
        INTENT_COMPLAINT,
        INTENT_LEGAL,
        INTENT_DISTRESS,
        INTENT_AUTH,
        INTENT_INJECTION,
    }
)

# Below this, an intent is not acted on even when it is nominally safe.
MIN_CONFIDENCE = 0.6

_MAX_INPUT_CHARS = 4000


@dataclass(frozen=True)
class Classification:
    intent: str
    confidence: float
    must_escalate: bool
    escalation_reason: Optional[str]
    language: str
    source: str  # "rules" | "rules+model"

    @property
    def is_safe(self) -> bool:
        return (
            not self.must_escalate
            and self.intent in SAFE_INTENTS
            and self.confidence >= MIN_CONFIDENCE
        )


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

_WORD = re.compile(r"[^a-z0-9àâäçéèêëîïôöùûüÿñœæ]+")


def _normalise(text: str) -> str:
    """Lowercased, punctuation flattened to spaces, padded for word matching."""
    lowered = str(text or "").lower()[:_MAX_INPUT_CHARS]
    return " " + _WORD.sub(" ", lowered).strip() + " "


def _hits(padded: str, needles: tuple[str, ...]) -> int:
    """How many of these markers appear as whole words / phrases."""
    return sum(1 for n in needles if f" {n} " in padded)


# ---------------------------------------------------------------------------
# Language
# ---------------------------------------------------------------------------

# Words that occur constantly in one language and (near-)never in the other.
# Cross-language collisions ("a", "on", "no", "or", "de" in an English
# sentence) are deliberately absent from both lists — a marker that fires for
# both sides is not evidence.
_FR_MARKERS = (
    "bonjour", "bonsoir", "salut", "merci", "svp", "plait", "plaît",
    "je", "j", "moi", "mon", "ma", "mes", "nous", "vous", "votre", "vos",
    "le", "la", "les", "un", "une", "des", "du", "au", "aux", "ce", "cette",
    "est", "sont", "suis", "etes", "êtes", "avez", "ai", "ont", "ete", "été",
    "pas", "pourquoi", "comment", "quand", "quelle", "quelles", "quel", "quels",
    "combien", "où", "sur", "avec", "pour", "et", "mais", "tres", "très",
    "toutes", "tous", "aidez", "aide", "besoin", "commande", "compte", "solde",
    "argent", "heure", "heures", "ouvert", "ouverts", "ouvrez", "ouverture",
    "vais", "veux", "voudrais", "donne", "porte", "plainte", "avocat",
    "justice", "saisir", "documents", "identite", "identité", "quelqu",
    "pirate", "vole", "reste", "sommes", "jours", "encore", "deja", "déjà",
)
_EN_MARKERS = (
    "hello", "hi", "hey", "thanks", "thank", "please",
    "you", "your", "yours", "my", "me", "i", "we", "our", "us",
    "is", "are", "was", "were", "be", "been", "am", "have", "has", "had",
    "do", "does", "did", "what", "when", "where", "why", "how", "which", "who",
    "will", "would", "can", "could", "should", "the", "and", "but", "for",
    "with", "from", "this", "that", "there", "they", "them", "someone",
    "something", "order", "account", "balance", "money", "help", "open",
    "opening", "hours", "time", "take", "made", "left", "feed", "children",
    "court", "lawyer", "contact", "driver", "food", "cold", "rude",
    "unacceptable", "rejected", "stole", "stolen", "fraudulent", "charged",
    "twice", "every", "day", "arrive", "minutes", "way", "welcome",
)

# An accented character is strong French evidence on its own.
_FR_ACCENTS = re.compile(r"[àâäçéèêëîïôöùûüÿœæ]")

# Two markers is the floor. One is noise — "how" appears in pidgin, "des"
# appears in nothing. A tie is unknown, not a coin flip.
_LANGUAGE_FLOOR = 2


def detect_language(text: str) -> str:
    padded = _normalise(text)
    fr = _hits(padded, _FR_MARKERS)
    en = _hits(padded, _EN_MARKERS)
    if _FR_ACCENTS.search(str(text or "").lower()):
        fr += 2
    if fr >= _LANGUAGE_FLOOR and fr > en:
        return LANG_FR
    if en >= _LANGUAGE_FLOOR and en > fr:
        return LANG_EN
    return LANG_UNKNOWN


# ---------------------------------------------------------------------------
# Intent vocabularies
#
# Order matters below: the first category that hits wins, so the ones whose
# mishandling is most expensive are tested first. Every one of them only
# decides *which* human reason is recorded — they all escalate.
# ---------------------------------------------------------------------------

_INJECTION = (
    "ignore your instructions", "ignore all instructions",
    "ignore previous instructions", "ignore the above", "disregard your",
    "disregard the above", "developer mode", "system prompt", "you are now",
    "act as", "jailbreak", "print the account", "reveal your",
    "ignore toutes les instructions", "ignore les instructions",
    "oublie tes instructions", "mode developpeur", "mode développeur",
)

_FRAUD = (
    "fraud", "fraude", "fraudulent", "frauduleuse", "scam", "arnaque",
    "hacked", "hack", "pirate", "piraté", "stolen", "stole", "steal",
    "unauthorized", "unauthorised", "non autorise", "non autorisé",
    "vole", "volé", "voler", "usurpation", "phishing",
)
_KYC = (
    "kyc", "identity", "identite", "identité", "id document", "id documents",
    "documents", "document", "cni", "passport", "passeport", "selfie",
    "verification rejected", "verification refused", "compte bloque",
    "compte bloqué", "account blocked", "account suspended", "suspendu",
    "onboarding", "justificatif",
)
_MONEY = (
    "balance", "solde", "refund", "refunded", "rembours", "remboursement",
    "payment", "paiement", "paid", "paye", "payé", "charged", "charge",
    "invoice", "facture", "montant", "amount", "transfer", "transfert",
    "virement", "transaction", "wallet", "portefeuille", "fcfa", "xaf",
    "money", "argent", "withdraw", "retrait", "deposit", "depot", "dépôt",
    "total", "price", "prix", "cost", "frais", "commission", "debited",
    "debite", "débité", "credited", "double charge", "charged twice",
)
_LEGAL = (
    "lawyer", "avocat", "court", "tribunal", "justice", "sue", "sued",
    "legal action", "poursuite", "poursuites", "huissier", "attorney",
    "regulator", "cobac", "beac", "police",
)
_DISTRESS = (
    "desespere", "désespéré", "desesperee", "supplie", "suicide", "starving",
    "no money left", "nothing to eat", "rien a manger", "rien à manger",
    "feed my children", "nourrir mes enfants", "help me please",
    "aidez moi", "aidez-moi", "je vous en supplie", "emergency", "urgence",
    "dying", "mourir",
)
_COMPLAINT = (
    "complaint", "plainte", "reclamation", "réclamation", "unacceptable",
    "inadmissible", "inacceptable", "scandaleux", "scandal", "rude",
    "impoli", "terrible", "awful", "worst", "disgusting", "degoutant",
    "dégoûtant", "angry", "furieux", "furieuse", "never again",
    "plus jamais", "cold", "froid", "late again",
)
_AUTH = (
    "otp", "one time password", "code de verification", "code de vérification",
    "verification code", "login code", "security code", "code secret",
    "my code", "mon code", "resend the code", "renvoyer le code",
)

_ESCALATION_ORDER: tuple[tuple[str, tuple[str, ...]], ...] = (
    (INTENT_INJECTION, _INJECTION),
    (INTENT_AUTH, _AUTH),
    (INTENT_FRAUD, _FRAUD),
    (INTENT_KYC, _KYC),
    (INTENT_MONEY, _MONEY),
    (INTENT_LEGAL, _LEGAL),
    (INTENT_DISTRESS, _DISTRESS),
    (INTENT_COMPLAINT, _COMPLAINT),
)

_OPENING_HOURS = (
    "opening hours", "open hours", "what time do you open", "what time you open",
    "when do you open", "closing time", "still open", "are you open",
    "heures d ouverture", "heure d ouverture", "horaires", "horaire",
    "quelle heure", "vous ouvrez", "vous fermez", "ouvert", "ouverture",
    "opening", "open today", "open now",
)
_HOW_IT_WORKS = (
    "how does it work", "how does the app work", "how do i", "how to",
    "how it works", "how can i use", "comment ca marche", "comment ça marche",
    "comment faire", "comment utiliser", "comment fonctionne", "fonctionne",
    "tutoriel", "tutorial", "guide",
)
_ORDER_STATUS = (
    "where is my order", "my order", "order status", "track my order",
    "delivery status", "where is my delivery", "ma commande", "ou est ma commande",
    "où est ma commande", "suivi de commande", "statut de ma commande",
    "livraison", "delivery", "eta",
)
_GREETING = (
    "hello", "hi", "hey", "good morning", "good evening",
    "bonjour", "bonsoir", "salut", "coucou",
)

_SAFE_ORDER: tuple[tuple[str, tuple[str, ...]], ...] = (
    (INTENT_OPENING_HOURS, _OPENING_HOURS),
    (INTENT_ORDER_STATUS, _ORDER_STATUS),
    (INTENT_HOW_IT_WORKS, _HOW_IT_WORKS),
    (INTENT_GREETING, _GREETING),
)


def _confidence(hits: int) -> float:
    return min(0.6 + 0.1 * hits, 0.95)


def classify(text: str, *, model_intent: Optional[str] = None) -> Classification:
    """Intent, confidence, language, and the flag that overrides all of them."""
    padded = _normalise(text)
    language = detect_language(text)

    for intent, vocabulary in _ESCALATION_ORDER:
        hits = _hits(padded, vocabulary)
        if hits:
            return Classification(
                intent=intent,
                confidence=_confidence(hits),
                must_escalate=True,
                escalation_reason=intent,
                language=language,
                source="rules",
            )

    if language == LANG_UNKNOWN:
        # Not a category — a comprehension failure. Same outcome.
        return Classification(
            intent=INTENT_UNKNOWN,
            confidence=0.0,
            must_escalate=True,
            escalation_reason="unknown_language",
            language=language,
            source="rules",
        )

    for intent, vocabulary in _SAFE_ORDER:
        hits = _hits(padded, vocabulary)
        if hits:
            return Classification(
                intent=intent,
                confidence=_confidence(hits),
                must_escalate=False,
                escalation_reason=None,
                language=language,
                source="rules",
            )

    # Nothing recognised. A model suggestion may propose one of the safe
    # intents here and nowhere else: it cannot clear a flag (every flagged
    # message returned above) and it cannot overrule a recognised intent.
    if model_intent in SAFE_INTENTS:
        return Classification(
            intent=model_intent,
            confidence=MIN_CONFIDENCE,
            must_escalate=False,
            escalation_reason=None,
            language=language,
            source="rules+model",
        )

    return Classification(
        intent=INTENT_UNKNOWN,
        confidence=0.0,
        must_escalate=False,
        escalation_reason=None,
        language=language,
        source="rules",
    )
