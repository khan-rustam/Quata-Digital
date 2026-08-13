"""The AI support layer — drafting, and the code that decides it never sends.

Three modules, kept apart so each one is testable on its own:

* ``provider``  — the model call, plus the kill switch in front of it. Works
  with no key configured, which is how QCP ships and how it stays until
  someone types one in.
* ``pii``       — what the model is allowed to *see*. Every prompt leaves
  Cameroon, so the customer's identifiers are stripped on the way in, before
  the call, while references to things (an order number) are kept so the
  layer can still help.
* ``facts``     — the seam a product implements to answer "what is the
  status of order X for this customer". The default implementation answers
  nothing, which is the correct behaviour while no product is connected —
  and is what makes ``respond``'s "no lookup, no claims" rule real.
* ``classify``  — what does this customer want, in French or English, and is
  it one of the categories a machine may never answer?
* ``respond``   — draft a reply for the intents that are safe, and refuse to
  produce text when any gate fails.

The seam this plugs into is ``conversations.assigned_agent`` /
``return_to_ai()``: this package answers "should a machine take this, and if
so what should it say?" and nothing else. It sends nothing. Delivery is still
``dispatch.send`` through ``routing.resolve_route``, which enforces the
account-purpose invariant and the service window on its own — this layer does
not route around any of it, and cannot: it produces a decision, not a ticket.

Ships inert. ``provider.ai_replies_enabled()`` is false unless
``QCP_AI_REPLIES_ENABLED`` is set in the environment **and** the
``whatsapp.ai_replies_enabled`` row is on, and it gates only this package —
turning it off stops every AI reply and stops nothing a human agent does.
"""
from __future__ import annotations

from . import classify, facts, pii, provider, respond  # noqa: F401

__all__ = ["classify", "facts", "pii", "provider", "respond"]
