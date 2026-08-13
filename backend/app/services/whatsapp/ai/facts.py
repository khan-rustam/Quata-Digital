"""The seam a product implements so the AI can look something up.

Today the AI knows nothing. It cannot answer "where is my order?" because
nothing in QCP has ever asked QuataFood, and every call site therefore passed
``facts=()`` as a literal. That is not a placeholder to be embarrassed about
— it is the reason the rule in ``respond`` is real: **no product system was
consulted, so no statement may be made about this customer's account, order,
payment, delivery or documents.** An empty fact set is what makes that rule
bite rather than being a sentence in a prompt.

So this module is the *contract*, not four integrations:

    class OrdersApi:
        def fetch(self, query: FactQuery) -> Sequence[Fact]:
            ...

    facts.register("quatafood", OrdersApi())

and the default implementation is ``NullFactSource``, which answers nothing.
**The null implementation is the correct behaviour today**, not a stub: no
product is connected to QCP, QCP itself is dormant, and a source that
invented an answer would be the exact failure this layer exists to prevent.

Three properties the implementation has to have, because of where it is
called from:

* **It never raises.** ``lookup`` is reached from ``turn.handle_inbound``,
  which is reached from webhook ingest, and ingest must return 200 to Meta
  or the subscription is disabled for the whole WABA. A product whose API is
  down produces *no facts*, which degrades to "the AI may not claim
  anything" — the safe direction.
* **What it returns is sanitised.** A product's fact travels to OpenAI in
  the United States exactly like the customer's message does, so a fact
  carrying a credential or a phone number is the same disclosure. Values go
  through ``pii.safe_fact_value``, which is the shared redactor's key rules
  plus the free-text sweep.
* **What it is asked is sanitised too.** The question handed to a product is
  the redacted text, so wiring a source cannot become a second copy of the
  customer's ID number in a second system's logs.

Registration is process-local and explicit. There is no auto-discovery and
no import-time hook: a product is connected to the AI by somebody typing a
line of code, which is the same deliberate act as creating the routing rule
that arms the send path.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Protocol, Sequence, runtime_checkable

from .pii import safe_fact_value
from .respond import Fact


log = logging.getLogger("quata.whatsapp.ai")

# A support reply is two or three sentences. More facts than this is a
# product dumping a record into a prompt, which is both a disclosure and a
# way to push the instructions out of the model's attention.
MAX_FACTS = 8


@dataclass(frozen=True)
class FactQuery:
    """What is being asked, and on whose behalf.

    ``text`` is **already redacted** — it is what ``pii.redact_customer_text``
    made of the customer's message. A product implementing ``fetch`` gets the
    customer's question, not their ID card number.
    """

    product_slug: str
    intent: str
    language: str
    phone_e164: str
    text: str
    conversation_id: Optional[int] = None


@runtime_checkable
class FactSource(Protocol):
    """What a product implements to answer for one of its customers.

    ``fetch`` returns the facts it can *prove* — each one carrying the API
    that answered, so a reply is traceable afterwards. Returning ``()`` is
    always a valid answer and means "I know nothing about this"; it must
    never mean "I could not reach my database", which is what raising is
    for.
    """

    def fetch(self, query: FactQuery) -> Sequence[Fact]:  # pragma: no cover - protocol
        ...


class NullFactSource:
    """The default for every product. Answers nothing, because nothing is known."""

    def fetch(self, query: FactQuery) -> Sequence[Fact]:
        return ()


NULL_SOURCE = NullFactSource()

_SOURCES: dict[str, FactSource] = {}


def register(product_slug: str, source: FactSource) -> None:
    """Connect a product's lookup to the AI layer. Explicit, and per process."""
    slug = str(product_slug or "").strip().lower()
    if not slug:
        raise ValueError("a fact source needs a product slug")
    if not callable(getattr(source, "fetch", None)):
        raise TypeError("a fact source must implement fetch(query)")
    _SOURCES[slug] = source


def unregister(product_slug: str) -> None:
    _SOURCES.pop(str(product_slug or "").strip().lower(), None)


def source_for(product_slug: Optional[str]) -> FactSource:
    """The product's source, or the null one. Never ``None``."""
    return _SOURCES.get(str(product_slug or "").strip().lower(), NULL_SOURCE)


def _clean(fact: object) -> Optional[Fact]:
    """One returned fact, or None if it is not usable as evidence."""
    key = str(getattr(fact, "key", "") or "").strip()
    source = str(getattr(fact, "source", "") or "").strip()
    value = getattr(fact, "value", None)
    if not key or not source or value is None:
        return None
    safe = safe_fact_value(key, value)
    if not str(safe).strip():
        return None
    return Fact(key=key, value=str(safe), source=source)


def lookup(query: FactQuery) -> tuple[Fact, ...]:
    """Ask the product what it knows. Returns ``()`` rather than raising.

    Every failure mode — no source registered, a source that explodes, a
    source that returns something that is not a fact — comes back as "no
    facts", and no facts means the reply may make no claim. That is the one
    direction this may fail in.
    """
    source = source_for(query.product_slug)
    try:
        found = source.fetch(query)
    except Exception as exc:  # noqa: BLE001 — ingest must survive a product outage
        # The exception *type* only: the message can carry the customer's
        # question or a connection string back out, and this is a log line.
        log.warning(
            "qcp.ai.facts: %s fact source failed (%s)",
            query.product_slug,
            type(exc).__name__,
        )
        return ()

    cleaned = []
    for item in list(found or ())[:MAX_FACTS]:
        fact = _clean(item)
        if fact is not None:
            cleaned.append(fact)
    return tuple(cleaned)
