"""The model call, and the two switches in front of it.

One job: turn a pair of prompts into text, or into a clear reason why there
is no text. It is the *only* place in QCP that talks to a language model, it
follows ``services/ai_cv.py`` (same ``OPENAI_*`` settings, same lazy import,
same "no key means unavailable, not broken"), and it deliberately does not
know what a conversation is. Deciding whether the text is safe to send is
``respond.py``'s job and happens after this returns.

**It never raises.** QCP ships with no key at all and will sit that way until
someone types one into the admin console, so "not configured" is the normal
state, not an error path — a caller that has to catch an exception for the
ordinary case eventually stops catching it. Every failure comes back as a
``Completion`` with a status.

**It never logs a key or a prompt.** Both reach the client call, and an
exception string is the one place they routinely come back out: an SDK that
echoes the request body turns a customer's phone number and order id into a
log line, and a misconfigured gateway echoes the Authorization header. So the
detail this module keeps from a failure is the exception's *type*, never its
message. What is logged is the type name, the model name and lengths.

**The kill switch.** ``ai_replies_enabled()`` is deliberately *not*
``settings_store.delivery_enabled()``. Delivery is the whole platform, human
agents included; this switch stops the machine drafting while leaving every
human agent working, which is what an incident actually needs. It is the same
env-AND-db shape as ``delivery_enabled`` and for the same reason (see
``settings_store``): a database row cannot start the AI on its own, and
``QCP_AI_REPLIES_ENABLED=false`` stops it with no redeploy and no DB write.
Both default to **off**, so the AI layer ships inert exactly like the rest of
QCP.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from app.core.config import settings as env_settings

from .. import settings_store


log = logging.getLogger("quata.whatsapp.ai")

# The kill switch is **not** implemented here. It has one implementation, in
# ``settings_store`` beside QCP's other runtime switches, and both this module
# and ``handover`` read that one — the build briefly had two spellings of it
# composed differently, which is the shape of the QuataPay ``is_production``
# failure. These two names are re-exported because callers and tests refer to
# them; they resolve to the switch's own constants, so a rename cannot leave
# half the readers behind.
ENV_AI_REPLIES = settings_store.ENV_AI_REPLIES
KEY_AI_REPLIES = settings_store.KEY_AI_REPLIES_ENABLED

STATUS_OK = "ok"
STATUS_NOT_CONFIGURED = "not_configured"
STATUS_ERROR = "error"

# A support reply is a WhatsApp message, not an essay. The bound is applied
# to the model request; an over-long answer is refused downstream rather than
# truncated, because a truncated sentence can invert its own meaning.
MAX_REPLY_CHARS = 700
_MAX_OUTPUT_TOKENS = 400
_TIMEOUT_SECONDS = 20


@dataclass(frozen=True)
class Completion:
    """What the model said, or why it said nothing.

    ``detail`` is safe to store: it is an exception *type* name or a short
    fixed string, never provider text and never anything the caller passed in.
    """

    status: str
    text: str = ""
    model: str = ""
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status == STATUS_OK and bool(self.text.strip())


def ai_replies_enabled() -> bool:
    """Master switch for AI drafting — ``settings_store.ai_replies_enabled``.

    Delegated, not re-derived. Stops the AI without stopping human agents:
    nothing the switch reads is consulted by ``dispatch``,
    ``conversations.assign`` or the agent console, so flipping it silences the
    machine and leaves the queue exactly as it was.
    """
    return settings_store.ai_replies_enabled()


def configured() -> bool:
    """Is there a model to call at all? Same key as ``ai_cv``."""
    return bool(env_settings.ai_enabled)


def model_name() -> str:
    return env_settings.OPENAI_MODEL


def complete(system_prompt: str, user_prompt: str) -> Completion:
    """One model call. Never raises, never logs a key or a prompt.

    The kill switch is deliberately *not* re-read here. This is the client;
    whether a customer may be answered at all is ``respond.draft``'s decision
    and it is taken before and after this call, on the same switch.
    """
    if not configured():
        return Completion(
            status=STATUS_NOT_CONFIGURED, model=model_name(), detail="no_openai_api_key"
        )

    try:
        from openai import OpenAI
    except ImportError:
        log.warning("qcp.ai: the openai package is not installed")
        return Completion(
            status=STATUS_NOT_CONFIGURED, model=model_name(), detail="openai_package_missing"
        )

    try:
        client = OpenAI(
            api_key=env_settings.OPENAI_API_KEY,
            base_url=env_settings.OPENAI_BASE_URL or None,
            timeout=_TIMEOUT_SECONDS,
        )
        resp = client.chat.completions.create(
            model=env_settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=_MAX_OUTPUT_TOKENS,
        )
        text = (resp.choices[0].message.content or "").strip()
    except Exception as exc:  # noqa: BLE001
        # The *type*, never the message: the message is where a key or a
        # customer's prompt comes back out. `log.exception` is wrong here for
        # the same reason — the traceback carries the arguments.
        kind = type(exc).__name__
        log.warning(
            "qcp.ai: model call failed (%s) model=%s prompt_chars=%d",
            kind,
            env_settings.OPENAI_MODEL,
            len(system_prompt) + len(user_prompt),
        )
        return Completion(status=STATUS_ERROR, model=model_name(), detail=kind)

    return Completion(status=STATUS_OK, text=text, model=env_settings.OPENAI_MODEL)
