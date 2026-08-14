"""QCP campaigns — the marketing side of the WhatsApp platform.

    audience ──► campaign (draft) ──► schedule ──► runner ──► dispatch.send
        │                                            │
        └── consent (opt-out) ◄──────────────────────┘
                    ▲
                    └── inbound "STOP" / "ARRÊT"

A campaign is an audience, an approved template, a schedule, a paced send and
a set of results. Five modules, one each:

``models``    the three tables. ``whatsapp_campaigns`` carries the same
              composite foreign keys ``whatsapp_messages`` does plus a CHECK
              pinning ``account_purpose='engagement'`` — a campaign row
              naming Quata Verify cannot exist.
``consent``   opt-out. The highest-priority signal in the package.
``audience``  who, derived only from QCP's own log. There is no customer
              database here and there must never be one.
``service``   the lifecycle: create (always a draft), schedule, start, pause,
              stop, results.
``runner``    the paced, per-message-stoppable send loop.

**It ships inert, like the rest of QCP.** A campaign is created ``draft``;
there is no parameter that makes it anything else. ``start`` refuses while
``settings_store.delivery_enabled()`` is false — the environment kill switch
AND the admin toggle — and every batch re-checks it, pausing a live campaign
if the switch is pulled mid-flight.

**It has no opinion about the two numbers.** Sending goes through
``dispatch.send``, so ``routing.resolve_route`` makes every decision about
which number, template and category are legal, exactly once, where it already
lives. What this package adds is that the *campaign row itself* cannot name
the authentication number — so the refusal exists at rest as well as in
flight.
"""
from __future__ import annotations

from . import audience, consent, runner, service
from .models import (
    WhatsAppCampaign,
    WhatsAppCampaignRecipient,
    WhatsAppOptOut,
)
from .service import CampaignRefused


__all__ = [
    "audience",
    "consent",
    "runner",
    "service",
    "CampaignRefused",
    "WhatsAppCampaign",
    "WhatsAppCampaignRecipient",
    "WhatsAppOptOut",
]
