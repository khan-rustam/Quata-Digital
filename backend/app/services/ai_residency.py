"""Where an AI request is allowed to go.

OWNER DECISION (2026-08-18): the AI runs on QUATA's own server. Customer
WhatsApp messages and job applicants' CVs stay in Cameroon.

WHY THIS IS A GUARD AND NOT A SETTING
-------------------------------------
Both AI paths build their client as::

    OpenAI(api_key=..., base_url=settings.OPENAI_BASE_URL or None)

`or None` means an unset, cleared or typo'd base URL silently falls back
to OpenAI's own servers in the United States. Nothing errors, nothing
logs, and customer data starts crossing a border again. Somebody clearing
the variable to debug a connection, or restoring an older `.env`, is
enough.

That is the same shape as every expensive bug found in this codebase this
month: an unsafe default reached by omission rather than by decision. So
the destination is checked at the moment of the call, and a request that
would leave the declared region is refused instead of sent.

WHY IT REFUSES THE CALL, NOT THE BOOT
--------------------------------------
Deliberately NOT a startup check. Making a mail-only setting a boot
requirement took QuataTrade's API down on 2026-08-18 — the box had never
set the variable, so the process refused to start and the API returned 502
for a day. A misconfigured AI must degrade the AI, not the platform.

So: the app always boots. A call that would breach residency returns
"not configured" the same way a missing key does, the support conversation
goes to a human, and the CV is reviewed by a person. Those are the
existing, working fallbacks.
"""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

#: Hostnames that are unambiguously this machine or this network.
_LOCAL_HOSTNAMES = frozenset({"localhost", "127.0.0.1", "::1", "0.0.0.0", "host.docker.internal"})

RESIDENCY_SELF_HOSTED = "self_hosted"
RESIDENCY_EXTERNAL = "external"


class ResidencyBreach(RuntimeError):
    """A request would have left the declared region."""


def _is_private_host(host: str) -> bool:
    """True when the host is this machine, a private address, or an
    internal name that cannot resolve outside our own network.

    A bare hostname with no dots (``ollama``, ``vllm``) is a container or
    LAN name — it cannot be a public endpoint, so it counts as local. A
    dotted public name does not, even if it looks internal: `ai.quata.cm`
    resolving somewhere abroad is exactly the mistake worth catching.
    """
    host = (host or "").strip().strip("[]").lower()
    if not host:
        return False
    if host in _LOCAL_HOSTNAMES:
        return True
    if "." not in host and ":" not in host:
        return True  # container / LAN short name
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return host.endswith((".local", ".internal", ".lan"))
    return addr.is_private or addr.is_loopback or addr.is_link_local


def destination_of(base_url: str | None) -> str:
    """Human-readable destination for logs and health. Never the full URL —
    a base URL can carry a token in a query string."""
    if not (base_url or "").strip():
        return "openai.com (default)"
    host = urlparse(base_url).hostname or "unknown"
    return f"{host} ({'self-hosted' if _is_private_host(host) else 'external'})"


def check(base_url: str | None, residency: str) -> None:
    """Raise `ResidencyBreach` if this call would leave the declared region.

    `self_hosted` is the owner's decision and therefore the default. Under
    it, an EMPTY base URL is a breach — that is the silent fallback to
    OpenAI, and it is the whole reason this function exists.
    """
    if (residency or RESIDENCY_SELF_HOSTED).strip().lower() != RESIDENCY_SELF_HOSTED:
        return

    url = (base_url or "").strip()
    if not url:
        raise ResidencyBreach(
            "AI is set to run on QUATA's own server, but no OPENAI_BASE_URL is "
            "configured — the client would default to OpenAI in the United "
            "States. Point OPENAI_BASE_URL at the self-hosted model, or set "
            "AI_DATA_RESIDENCY=external to allow calls abroad deliberately."
        )

    host = urlparse(url).hostname
    if not _is_private_host(host or ""):
        raise ResidencyBreach(
            f"AI is set to run on QUATA's own server, but OPENAI_BASE_URL points "
            f"at '{host}', which is outside our network. Customer messages and "
            "CVs would leave Cameroon. Point it at the self-hosted model, or set "
            "AI_DATA_RESIDENCY=external to allow this deliberately."
        )


__all__ = [
    "RESIDENCY_EXTERNAL",
    "RESIDENCY_SELF_HOSTED",
    "ResidencyBreach",
    "check",
    "destination_of",
]
