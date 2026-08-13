"""Runtime switches for QCP.

Five toggles, so they live in the **existing** ``site_settings`` table
under ``group="whatsapp"`` rather than in a ninth QCP table.

The one rule that matters:

    delivery_enabled() == env(WHATSAPP_ENABLED) AND db(whatsapp.delivery_enabled)

Env is a kill switch a DB toggle cannot override. This is the direct answer
to the audited QuataPay failure mode — credentials sitting in a production
table meant the rail was one admin form submission away from live with no
redeploy. Here, flipping every DB row still sends nothing unless the
environment says so, and turning the env var off stops delivery without a
code change. Same shape as
``services/notifications/settings_store.service_enabled``.

The DB key defaults to **false** when the row is absent, so a database that
has never been through the QCP admin console is dormant rather than
implicitly live.

``require_signature`` is floored the same way but in the opposite direction —
see its docstring. The rule for both: **env decides the unsafe direction, the
DB row may only move things the safe way.**

One thing here is not a switch: ``ai_reply_readiness``. A switch that is on
and does nothing is the worst state an operator can be left in, and the AI
reply switch has exactly that failure mode — an AI reply is a send, a send
needs a routing rule, and a missing rule refuses the reply deep inside
``dispatch`` where nobody watching the console can see it. So "is this switch
actually doing anything?" is answered here, next to the switch itself, in one
implementation the console banner and the worker both read.
"""
from __future__ import annotations

import os
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings as env_settings
from app.services import site_settings


GROUP = "whatsapp"

KEY_DELIVERY_ENABLED = "whatsapp.delivery_enabled"
KEY_API_VERSION = "whatsapp.api_version"
KEY_REQUIRE_SIGNATURE = "whatsapp.require_signature"
KEY_MAX_ATTEMPTS = "whatsapp.max_attempts"
KEY_AI_REPLIES_ENABLED = "whatsapp.ai_replies_enabled"

# The env floor for the AI switch, kept next to the DB key it is paired with.
# Named here rather than read with ``os.getenv`` in two places: this was
# genuinely spelled twice during the build (once in the drafting engine, once
# in the brake), which is the exact shape of the QuataPay ``is_production``
# failure — two spellings of one guard that drift until the looser one wins.
ENV_AI_REPLIES = "QCP_AI_REPLIES_ENABLED"

_TRUE = {"1", "true", "yes", "on"}


def _get(key: str, default: Optional[str] = None) -> Optional[str]:
    return site_settings.get_setting(key, default)


def _get_bool(key: str, default: bool) -> bool:
    raw = _get(key)
    if raw is None or raw == "":
        return default
    return str(raw).strip().lower() in _TRUE


def _get_int(key: str, default: int) -> int:
    raw = _get(key)
    if raw is None or raw == "":
        return default
    try:
        return int(str(raw).strip())
    except ValueError:
        return default


def delivery_enabled() -> bool:
    """Master switch: the env kill switch AND the admin toggle must agree."""
    if not env_settings.WHATSAPP_ENABLED:
        return False
    return _get_bool(KEY_DELIVERY_ENABLED, False)


def _ai_env_floor() -> bool:
    """``QCP_AI_REPLIES_ENABLED``, read live, with the boot value as fallback.

    The process environment is checked first so the switch can be pulled
    without a restart (and so a test can move it); ``Settings`` supplies the
    answer when the variable is not in the environment at all, which is how a
    value set in ``.env`` reaches this. Both read the same name, so the two
    can only agree — and the unsafe direction, an empty or unset variable, is
    the one that ends up **off** either way.
    """
    raw = os.getenv(ENV_AI_REPLIES)
    if raw is None or raw.strip() == "":
        return bool(env_settings.QCP_AI_REPLIES_ENABLED)
    return raw.strip().lower() in _TRUE


def ai_replies_enabled() -> bool:
    """May the support AI answer a customer by itself? **The** kill switch.

    One implementation, read by both halves of the AI layer — the drafting
    engine (``ai/provider.py``) and the brake (``handover.py``). Neither
    imports the other (a brake that imports the engine can be released by
    editing the engine); both import this, which is the module that already
    owns QCP's runtime switches.

    Three gates, all of which must agree:

    * ``QCP_AI_REPLIES_ENABLED`` — the AI's own env floor. Off stops every AI
      reply with no redeploy and no database write, and stops *only* AI
      replies: assignment, ``return_to_ai``, close, the agent console and the
      products' own OTP and order traffic are untouched.
    * ``WHATSAPP_ENABLED`` — the fleet kill switch. An AI reply is a send.
    * ``whatsapp.ai_replies_enabled`` — the admin toggle, absent → **false**.

    Deliberately *not* ``delivery_enabled``: an operator must be able to stop
    the bot without taking the Verify number's OTPs down with it.

    An OpenAI key is deliberately **not** one of the gates. A missing key is a
    missing capability, not an operator's instruction: with the switch on and
    no key the engine escalates the customer to a human, which is a better
    outcome than the silence "the switch is off" produces. Callers that need
    "can it actually draft?" ask ``env_settings.ai_enabled``.
    """
    if not _ai_env_floor():
        return False
    if not env_settings.WHATSAPP_ENABLED:
        return False
    return _get_bool(KEY_AI_REPLIES_ENABLED, False)


def api_version() -> str:
    return _get(KEY_API_VERSION, env_settings.WHATSAPP_API_VERSION) or "v21.0"


def require_signature() -> bool:
    """Env floor first: a DB row may add strictness, never remove it.

    The mirror image of ``delivery_enabled`` above, and env-floored for the
    same reason. There the unsafe state is *on*, so env AND db means no DB row
    can start delivery. Here the unsafe state is *off* — this one switch gates
    the internet-facing Meta webhook **and** the product ``X-QCP-Signature``
    check — so ``WHATSAPP_REQUIRE_SIGNATURE=true`` (the default) pins it on
    and a ``settings:manage`` PUT cannot undo it. Read as a DB default, one
    row would turn ``POST /whatsapp/webhook/{slug}`` into an unauthenticated
    write API: forged inbound messages, forged conversations on the Verify
    number, forged status callbacks marking real messages delivered.

    Below the floor (``WHATSAPP_REQUIRE_SIGNATURE=false``, the dev escape
    hatch) the admin toggle still decides, and still defaults to off. Note
    that reaching that state at all now takes an unconfigured, non-production
    box: ``Settings.assert_whatsapp_signature_floor`` refuses to boot below
    the floor if delivery is on, if any account holds credentials, or if
    ``ENVIRONMENT=production``.
    """
    if env_settings.WHATSAPP_REQUIRE_SIGNATURE:
        return True
    return _get_bool(KEY_REQUIRE_SIGNATURE, False)


def max_attempts() -> int:
    return max(_get_int(KEY_MAX_ATTEMPTS, env_settings.WHATSAPP_MAX_ATTEMPTS), 1)


# ---------------------------------------------------------------------------
# "The switch is on — is it doing anything?"
# ---------------------------------------------------------------------------

# Why the switch is not answering anybody. Stable codes, never free text, so
# the console can render a sentence per code and a test can pin one.
AI_BLOCKED_SWITCH_OFF = "ai_replies_disabled"
AI_BLOCKED_NO_PRODUCT = "no_enabled_product"
AI_BLOCKED_NO_ROUTE = "no_ai_routing_rule"


def ai_reply_readiness(db: Session) -> dict:
    """Can the support AI actually answer anybody, and if not, exactly why.

    ``ai_replies_enabled()`` answers "is the switch on". This answers the
    question an operator is really asking, which is not the same one: an AI
    reply is a send, every send crosses ``routing.resolve_route``, and with no
    active engagement rule for ``ai_support_reply`` every reply is refused as
    ``no_route`` inside ``dispatch``. What the operator sees is an AI that was
    switched on and answers nobody, with nothing on any screen saying so. That
    is this function's whole reason to exist — the state is *reported* rather
    than left to be inferred from an audit denial nobody is reading.

    **Both languages, per product.** Cameroon is francophone and anglophone,
    QCP supports ``en`` and ``fr`` (``handover.SUPPORTED_LANGUAGES``, read
    here rather than restated), and ``routing._find_rule`` matches on locale:
    an exact-locale rule beats the NULL "any language" rule, and a rule
    created for ``en`` alone returns *nothing* for a francophone thread. So a
    check that only asked "does a rule exist?" would call an English-only
    configuration healthy and leave every French-speaking customer silently
    unanswered. Each enabled product is therefore asked once **per supported
    locale**, and a partial answer is a gap.

    A rule is only counted when it would really carry the reply: active,
    unconditional (v1 treats non-empty ``conditions`` as ``no_route``), and
    ``engagement`` — an ``authentication`` rule is refused by ``ai.turn``
    before the send, because it would put a support sentence on Quata Verify.

    Selection is delegated to ``routing._find_rule`` rather than re-queried
    here, for the reason this module already exists: one implementation of a
    rule, not two that drift until the looser one wins.

    Returns, and every field is safe to render:

    ``enabled``           the switch itself
    ``can_answer``        on **and** every enabled product routed in both languages
    ``misconfigured``     on and **not** able to answer — the loud state
    ``blocker``           one of the ``AI_BLOCKED_*`` codes, or ``None``
    ``gaps``              ``[{"product": slug, "locales": [...]}]`` — what to fix
    ``routed_products``   the enabled products that are fully routed
    ``intent``            the rule an operator has to create
    ``locales``           the languages it has to cover

    Off is **not** misconfigured. The fleet is dormant by design and a
    dormant install must not raise an alarm; only a switch that is on and
    powerless does.
    """
    from app.models import WhatsAppProduct  # noqa: PLC0415

    from .ai.turn import AI_REPLY_INTENT  # noqa: PLC0415
    from .handover import SUPPORTED_LANGUAGES  # noqa: PLC0415
    from .routing import PURPOSE_ENGAGEMENT, _find_rule  # noqa: PLC0415

    enabled = ai_replies_enabled()
    locales = sorted(SUPPORTED_LANGUAGES)

    products = (
        db.query(WhatsAppProduct)
        .filter(WhatsAppProduct.is_enabled == True)  # noqa: E712
        .order_by(WhatsAppProduct.slug)
        .all()
    )

    routed: list[str] = []
    gaps: list[dict] = []
    for product in products:
        missing = [
            locale
            for locale in locales
            if not _routes_ai_replies(
                _find_rule(
                    db,
                    product_id=product.id,
                    intent=AI_REPLY_INTENT,
                    locale=locale,
                ),
                engagement=PURPOSE_ENGAGEMENT,
            )
        ]
        if missing:
            gaps.append({"product": product.slug, "locales": missing})
        else:
            routed.append(product.slug)

    if not enabled:
        blocker: Optional[str] = AI_BLOCKED_SWITCH_OFF
    elif not products:
        blocker = AI_BLOCKED_NO_PRODUCT
    elif gaps:
        blocker = AI_BLOCKED_NO_ROUTE
    else:
        blocker = None

    return {
        "enabled": enabled,
        "can_answer": enabled and blocker is None,
        "misconfigured": enabled and blocker is not None,
        "blocker": blocker,
        "gaps": gaps,
        "routed_products": routed,
        "intent": AI_REPLY_INTENT,
        "locales": locales,
    }


def _routes_ai_replies(rule, *, engagement: str) -> bool:
    """Would this rule actually carry an AI reply? Mirrors ``resolve_route``."""
    if rule is None:
        return False
    if rule.conditions or {}:
        return False
    return rule.purpose == engagement
