"""One inbound message, from "a customer said something" to "and then what".

This is the wiring the AI support layer was missing: ``webhooks`` ingests and
commits a message, then hands the *committed* thread to ``handle_inbound``
below, which is the only thing in QCP that composes a reply without a human
in the loop. Everything it does is off by default — see the first line of
``handle_inbound`` — and everything it decides is somebody else's rule
enforced here in one place:

    brake  →  engine  →  guard  →  route  →  send

* **brake** — ``handover.decide``. Runs *before* the model, on signals the
  classifier produced from code and on the customer's own words. It is the
  thing that says "a human takes this", and it never sees model output, so
  nothing the model writes can release it.
* **engine** — ``respond.draft``. Applies its own way-in gates again (the
  Verify number, the escalation vocabularies, the service window) and then
  the way-out gates on whatever the model said.
* **guard** — ``handover.guard_ai_send``, which raises rather than returning
  a flag, because the correct handling of "the AI tried to send an OTP" is
  that nothing leaves the building.
* **route** — the rule the reply resolves through must itself be an
  *engagement* rule. ``routing`` picks the account from the rule's purpose,
  not from the thread's, so a rule pointing at ``authentication`` would put
  an AI-composed sentence on Quata Verify however ordinary the thread looked.
  Refused here, before ``dispatch`` is called at all.
* **send** — ``dispatch.send``, the one send path. Every routing refusal,
  redaction rule and the dormancy gate still apply, and while QCP is dormant
  the honest outcome is ``suppressed``.

**Nothing here is trusted to be the only check.** The engine re-reads the
account purpose from storage, the guard re-reads it again, routing refuses
free-form on the Verify number for a third time, and the database has a
``ck_whatsapp_messages_no_freeform_on_verify`` constraint underneath all of
them. Four layers, because the cost of getting this one wrong is the fleet's
OTP number being restricted and four products losing account recovery.

**It never raises.** It is called from ingest, and ingest must return 200 to
Meta or the subscription gets disabled for the whole WABA. Every failure is
an escalation to a human plus an audit row.
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models import WhatsAppAccount, WhatsAppConversation, WhatsAppProduct

from .. import audit, conversations, handover, routing, settings_store
from . import classify as classifier
from . import facts as fact_seam
from . import pii, provider, respond


log = logging.getLogger("quata.whatsapp.ai")

PURPOSE_ENGAGEMENT = "engagement"

# The intent an AI-composed support reply is addressed with. It has to resolve
# through a routing rule like every other send, which is one more reason the
# feature is inert on a fresh install: no rule, no route, no message. An
# operator creating this rule is the deliberate act that arms the AI, and the
# rule's purpose is checked below rather than trusted.
AI_REPLY_INTENT = "ai_support_reply"


def _escalate(
    db: Session,
    conversation: WhatsAppConversation,
    *,
    reason: str,
    product_id: Optional[int],
    model: Optional[str] = None,
    detail: Optional[dict] = None,
    now=None,
) -> dict:
    """Queue a human, audit it, and say so. The only failure mode here."""
    decision = handover.Decision(
        action=handover.ACT_ESCALATE, reason=reason, triggers=(reason,), detail=detail or {}
    )
    handover.apply(
        db,
        conversation,
        decision,
        product_id=product_id,
        model=model,
        prompt_version=respond.PROMPT_VERSION,
        now=now,
    )
    return {"action": handover.ACT_ESCALATE, "reason": reason}


def handle_inbound(
    db: Session,
    *,
    account: WhatsAppAccount,
    conversation: WhatsAppConversation,
    product_id: Optional[int],
    text: str,
    source_ip: Optional[str] = None,
    now=None,
) -> dict:
    """Decide, and possibly answer, one inbound customer message.

    ``account`` and ``product_id`` are the values ingest already computed —
    the account the message physically arrived on, and the attribution
    ``conversations.attribute_inbound`` returned, whose supported answer
    ``None`` means "two products are in play and the ownership model refuses
    to guess". Neither is taken from anything a caller composed.

    Returns a small dict describing what happened; the caller logs it and
    otherwise ignores it. Commits nothing — ingest owns the transaction.
    """
    # The kill switch, first and cheapest. Off is the shipping state, and off
    # means this function is a *no-op*: no draft, no escalation, no audit row,
    # nothing written. Auditing "the AI is off" on every inbound would write a
    # row per customer message forever, and a dormant platform that queues a
    # human for every message is not dormant.
    if not settings_store.ai_replies_enabled():
        return {"action": "off"}

    try:
        return _turn(
            db,
            account=account,
            conversation=conversation,
            product_id=product_id,
            text=text,
            source_ip=source_ip,
            now=now,
        )
    except Exception as exc:  # noqa: BLE001 — ingest must survive anything
        # The type only. An exception message from this path can carry the
        # customer's own words back out, and this is a log line.
        log.warning("qcp.ai.turn failed (%s)", type(exc).__name__)
        try:
            return _escalate(
                db,
                conversation,
                reason=handover.R_PROVIDER_ERROR,
                product_id=product_id,
                detail={"error_type": type(exc).__name__},
                now=now,
            )
        except Exception:  # noqa: BLE001 — a failed escalation is not a 500 to Meta
            log.warning("qcp.ai.turn could not even escalate")
            return {"action": "error"}


def _signals(classification: classifier.Classification) -> handover.Signals:
    """The engine's read of the message, in the brake's vocabulary.

    Every field is derived from ``classify`` — deterministic keyword code that
    runs before the model and cannot be argued out of its answer by the
    message it is classifying. ``wants_human`` is left False on purpose:
    ``handover.decide`` reads that from the customer's own text itself, and
    two detectors for one signal is one detector that can be forgotten.
    """
    return handover.Signals(
        understood=classification.intent != classifier.INTENT_UNKNOWN,
        unsafe=classification.must_escalate,
        confidence=float(classification.confidence),
        language=(
            classification.language
            if classification.language in handover.SUPPORTED_LANGUAGES
            else None
        ),
        wants_human=False,
        # No key is not an outage, but it has the same consequence for this
        # customer: nothing is going to answer them unless a person does.
        provider_error=not provider.configured(),
        topics=(),
        asserts_facts=False,
        facts_from_product_api=False,
    )


def _turn(
    db: Session,
    *,
    account: WhatsAppAccount,
    conversation: WhatsAppConversation,
    product_id: Optional[int],
    text: str,
    source_ip: Optional[str],
    now,
) -> dict:
    from .. import dispatch  # noqa: PLC0415 — late, so ingest-only processes stay light

    classification = classifier.classify(text)

    # 1 ─ the brake. Before the model, and it is what decides "a human".
    gate = handover.decide(
        db,
        conversation,
        signals=_signals(classification),
        account_purpose=account.purpose,
        product_id=product_id,
        text=text,
        now=now,
    )
    if not gate.may_reply:
        handover.apply(
            db,
            conversation,
            gate,
            product_id=product_id,
            prompt_version=respond.PROMPT_VERSION,
            now=now,
        )
        return {"action": gate.action, "reason": gate.reason}

    # 2 ─ the lookup. ``facts.lookup`` asks whatever the product registered
    #     for this slug; the default is ``NullFactSource``, which answers
    #     nothing, and no product is connected to QCP today — so on a real
    #     install this returns ``()`` and that is the *correct* answer, not a
    #     gap. It never raises: a product outage degrades to "no facts",
    #     which the output gates read as "no claims permitted".
    #
    #     The question handed to the product is the redacted text, so wiring
    #     a source cannot make a second copy of the customer's ID number in a
    #     second system. Redacted the *same way* the prompt is, authentication
    #     context included: one message must not mean two different things to
    #     two readers in the same turn.
    product = db.get(WhatsAppProduct, product_id) if product_id else None
    retrieved = fact_seam.lookup(
        fact_seam.FactQuery(
            product_slug=product.slug if product is not None else "",
            intent=classification.intent,
            language=classification.language,
            phone_e164=conversation.phone_e164,
            text=pii.redact_customer_text(
                text,
                after_auth_message=respond.authentication_recently_sent(
                    db, conversation, now=now
                ),
            ),
            conversation_id=conversation.id,
        )
    )

    # 3 ─ the engine. Writes its own audit row for the decision it takes.
    #
    #     With an empty fact list the output gates refuse any draft
    #     containing a digit run at all, and confine the reply to a
    #     pleasantry, a question, a handover or a statement about QUATA
    #     itself — every figure and every claim in such a draft was invented.
    decision = respond.draft(db, conversation, text, facts=retrieved, now=now)
    if not decision.sends_message:
        return _escalate(
            db,
            conversation,
            reason=decision.reason,
            product_id=product_id,
            model=decision.model or None,
            detail={"intent": decision.intent, "language": decision.language},
            now=now,
        )

    # 4 ─ the send guard. Raises; an AI trying to send an OTP is not a flag.
    try:
        handover.guard_ai_send(
            account_purpose=account.purpose,
            kind=decision.kind,
            intent=AI_REPLY_INTENT,
            body=decision.text,
            grounded=decision.grounded,
        )
    except handover.AiSendRefused as refused:
        return _escalate(
            db,
            conversation,
            reason="send_guard_refused",
            product_id=product_id,
            model=decision.model or None,
            # The refusal names the rule, never the body it refused.
            detail={"refusal": str(refused).split(":", 1)[0]},
            now=now,
        )

    if product is None:
        return _escalate(
            db, conversation, reason=handover.R_UNATTRIBUTED, product_id=None, now=now
        )

    # 5 ─ the route's own purpose. ``routing`` selects the account from the
    #     rule, not from this thread, so an ``authentication`` rule would put
    #     this sentence on Quata Verify however ordinary the thread looks.
    #     Read through routing's own selector — one selection implementation,
    #     not two — and used only to refuse.
    rule = routing._find_rule(  # noqa: SLF001
        db, product_id=product.id, intent=AI_REPLY_INTENT, locale=conversation.locale or None
    )
    if rule is not None and rule.purpose != PURPOSE_ENGAGEMENT:
        return _escalate(
            db,
            conversation,
            reason="authentication_route_forbidden",
            product_id=product.id,
            model=decision.model or None,
            detail={"intent": AI_REPLY_INTENT, "purpose": rule.purpose},
            now=now,
        )

    # 6 ─ the one send path. Routing, redaction and the dormancy gate all
    #     still apply; while QCP is dormant this comes back ``suppressed``.
    result = dispatch.send(
        product_slug=product.slug,
        intent=AI_REPLY_INTENT,
        to_phone_e164=conversation.phone_e164,
        kind=respond.KIND_TEXT,
        locale=conversation.locale,
        body=decision.text,
        reference=f"ai:{uuid.uuid4().hex}",
        source_ip=source_ip,
    )

    message_uid = result.get("message_uid")
    if message_uid and not result.get("duplicate"):
        conversations.attach_outbound(
            db,
            product=product,
            message_uid=message_uid,
            phone_e164=conversation.phone_e164,
            thread=conversation,
        )
        # The authorship seam the agent console reads back: an ``ai.*`` audit
        # row against the message uid is what makes an outbound row show in a
        # transcript as the bot's words rather than a colleague's.
        audit.record(
            db,
            action="ai.sent",
            resource_type="whatsapp_message",
            resource_id=message_uid,
            outcome=audit.OUTCOME_OK if result.get("ok") else audit.OUTCOME_ERROR,
            reason=result.get("reason") or decision.reason,
            account_id=account.id,
            product_id=product.id,
            details={
                "conversation_id": conversation.id,
                "model": decision.model,
                "prompt_version": decision.prompt_version,
                "intent": decision.intent,
                "language": decision.language,
                "grounded": decision.grounded,
                "fact_sources": list(decision.fact_sources),
                "status": result.get("status"),
            },
        )
    return {
        "action": "answered",
        "reason": decision.reason,
        "status": result.get("status"),
        "message_uid": message_uid,
    }
