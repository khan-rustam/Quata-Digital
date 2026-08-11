"""Making provider text safe to write down.

Meta writes its own error strings, and it echoes back what it was sent. A
rejected call comes home quoting the token — whole, truncated, URL-escaped,
JSON-escaped, behind a ``Bearer``, or hanging off a signed media URL it wants
us to retry. That string is then written down.

There are **two** doors, not one, and that is why this lives in its own module
rather than inside ``meta.py``:

* the **send** path — ``meta._call`` → ``dispatch._record_failure`` →
  ``whatsapp_messages.last_error``, ``whatsapp_accounts.last_error``, an audit
  ``reason``, and the dict the admin console renders;
* the **status webhook** — ``webhooks._ingest_status`` →
  ``whatsapp_delivery_events.error_title`` / ``error_detail`` / ``raw`` and,
  again, ``whatsapp_messages.last_error``. Meta authors that text as surely as
  it authors a send rejection.

``webhooks.py`` may not import ``meta.py`` — that is asserted by
``tests/test_whatsapp_boundaries.py``, because exactly one module is allowed
to reach the transport. So the scrubber cannot live in the transport if both
doors are to use it. It lives here; ``meta`` re-exports it for the callers
that already reach it that way.

The rule is **shape, not equality**. Anything that looks like a credential is
removed whether or not we hold a copy to compare it against. An exact-match
replacement is kept as well, because a credential with no recognisable shape
(an operator's hand-made verify token) has no other defence.

The opposite failure matters too. A scrub that reduces every failure to
``"***"`` makes ``last_error`` worthless, and the next person to debug a
delivery failure deletes the column. Meta's ordinary text — error numbers,
prose, phone number ids, WABA ids, ``fbtrace_id`` — must survive intact, so
every rule below is anchored on something a sentence does not contain.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any, Optional


REDACTED = "***"

# The shortest run of a credential worth treating as a disclosure. Twelve
# characters of a Meta access token is far more than "the first few", and no
# ordinary English error text collides with it.
FRAGMENT_FLOOR = 12

# Parameter and field names that introduce a credential by declaration. Order
# matters only in that the longer alternatives come first.
_SENSITIVE_NAME = (
    r"(?:appsecret[_\-]?proof|access[_\-\s]?token|client[_\-]?secret|app[_\-]?secret"
    r"|refresh[_\-]?token|auth[_\-]?token|verify[_\-]?token|session[_\-]?key"
    r"|api[_\-]?key|signature|password|secret|token|sig)"
)

# Value characters a credential may be carrying by the time Meta echoes it:
# base64url, plus the ``%`` of a URL-escaped copy and the ``\/`` of a
# JSON-escaped one.
_CRED_CHARS = r"A-Za-z0-9._~+/=\-%\\"

_SHAPED_CREDENTIALS: tuple[tuple[re.Pattern[str], str], ...] = (
    # 1 ─ a credential riding a query string. Meta hands back signed media
    #     URLs with the token still attached. The parameter name is kept so
    #     the reader can see *what* was removed.
    (
        re.compile(rf"(?i)([?&][A-Za-z0-9_\-.]*{_SENSITIVE_NAME}[A-Za-z0-9_\-.]*=)[^&\s\"'<>]+"),
        r"\1" + REDACTED,
    ),
    # 2 ─ the same, declared as a JSON field or a header line. Sixteen
    #     characters minimum: "access token: Session has expired" must not
    #     lose the word that explains the failure.
    (
        re.compile(rf"(?i)({_SENSITIVE_NAME}\\?\"?\s*[:=]\s*\\?\"?)[{_CRED_CHARS}]{{16,}}"),
        r"\1" + REDACTED,
    ),
    # 3 ─ an Authorization header value.
    (
        re.compile(rf"(?i)\b(bearer|basic|oauth)\s+[{_CRED_CHARS}]{{12,}}"),
        r"\1 " + REDACTED,
    ),
    # 4 ─ a Meta access token by its own prefix (user, page, system-user and
    #     app tokens all begin ``EAA``). This is the rule that survives
    #     escaping and truncation, because it keys on the head of the value
    #     rather than on the whole of it.
    (re.compile(rf"(?i)\bEAA[{_CRED_CHARS}]{{{FRAGMENT_FLOOR},}}"), REDACTED),
    # 5 ─ an app secret (32 hex) or an appsecret_proof (64 hex), naked.
    (re.compile(r"\b[0-9a-fA-F]{32,}\b"), REDACTED),
    # 6 ─ an app access token, ``<app_id>|<app_secret>``.
    (re.compile(r"\b\d{6,}\|[A-Za-z0-9_\-]{16,}"), REDACTED),
)

# 7 ─ the catch-all. A long opaque run with no recognisable prefix at all —
#     a session key, a rotated credential in a format Meta has not shipped
#     yet. Held to a high bar so it never eats prose: 32+ characters with no
#     separators, both letters and digits, and Shannon entropy per character
#     that no English word reaches.
_OPAQUE_FLOOR = 32
_ENTROPY_FLOOR = 3.0
_OPAQUE_RUN = re.compile(rf"[A-Za-z0-9_\-]{{{_OPAQUE_FLOOR},}}")


def _looks_opaque(run: str) -> bool:
    if not (any(c.isdigit() for c in run) and any(c.isalpha() for c in run)):
        return False
    total = len(run)
    counts = Counter(run)
    entropy = -sum((n / total) * math.log2(n / total) for n in counts.values())
    return entropy >= _ENTROPY_FLOOR


def _strip_known(value: str, secrets: tuple[Optional[str], ...]) -> str:
    """Remove any supplied credential, whole or truncated to a prefix.

    Longest prefix first, so the replacement is maximal rather than leaving
    the tail of a token behind.
    """
    for secret in secrets:
        if not secret or len(secret) < FRAGMENT_FLOOR:
            continue
        for size in range(len(secret), FRAGMENT_FLOOR - 1, -1):
            fragment = secret[:size]
            if fragment in value:
                value = value.replace(fragment, REDACTED)
                break
    return value


def scrub_provider_text(text: Optional[str], *secrets: Optional[str]) -> str:
    """Make one string of provider text safe to write down.

    Call this at **every** sink where provider text stops being transient:
    a persisted column, an audit row, a log record, or a value returned to a
    caller. ``secrets`` is optional — the shape rules stand on their own, and
    passing the credentials we happen to hold only adds the exact-match belt.
    """
    value = str(text or "")
    if not value:
        return value
    value = _strip_known(value, secrets)
    for pattern, replacement in _SHAPED_CREDENTIALS:
        value = pattern.sub(replacement, value)
    return _OPAQUE_RUN.sub(
        lambda m: REDACTED if _looks_opaque(m.group(0)) else m.group(0), value
    )


def scrub_structure(value: Any, *secrets: Optional[str]) -> Any:
    """``scrub_provider_text`` over every string inside a nested structure.

    The webhook stores Meta's raw status object, so a credential in a field
    nobody named is still a credential in a row. Keys are scrubbed as well as
    values: a JSON object keyed by a token is as much a disclosure as one
    valued by it.
    """
    if isinstance(value, str):
        return scrub_provider_text(value, *secrets)
    if isinstance(value, dict):
        return {
            scrub_provider_text(str(k), *secrets): scrub_structure(v, *secrets)
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [scrub_structure(v, *secrets) for v in value]
    return value
