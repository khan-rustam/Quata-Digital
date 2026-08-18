"""AI talent-intelligence engine (HRMS 1E) — OpenAI-backed CV analysis.

Disabled unless ``OPENAI_API_KEY`` is set. The openai client is imported
lazily so the app boots (and tests run) without the key or package configured.

The prompt this module builds leaves Cameroon — ``client.chat.completions``
posts it to OpenAI in the United States — and it is built from the *whole*
uploaded CV. So the CV is filtered on the way **in**, before the call, by
``redact_cv_text`` below. Read its docstring before changing anything on that
path: it states which categories are removed, which are deliberately kept,
and what still crosses the border after the filter.
"""
from __future__ import annotations

from app.services import ai_residency

import json
import logging
import re
from pathlib import Path

from app.core.config import settings

# The free-text redactor is reused, not reimplemented: phones (every
# Cameroonian notation, including the spaced ones whose separator hole was
# found and closed), emails, card PANs and labelled CNI/NIU/passport numbers
# are that module's rules and stay that module's rules. A second copy of them
# here would be a third redactor and would reintroduce the hole.
#
# RESOLVED (2026-08-17, reconciliation pass) — this used to import
# ``app.services.whatsapp.ai.pii``, which tripped
# tests/test_whatsapp_boundaries.py: nothing outside the QCP package may import
# a QCP submodule, because reaching past the facade is how a caller mints or
# bypasses a ticket. Rather than widening that allow-list, the free-text engine
# — pure regex, no transport, no DB, no routing, and generic PII rather than
# anything WhatsApp-specific — was moved to ``app/services/pii_text.py``, which
# both packages now import. ``whatsapp/ai/pii.py`` re-exports it unchanged and
# keeps ``safe_fact_value``, the half that genuinely needs the QCP key rules.
# Side benefit: analysing a CV no longer drags whatsapp.ai's __init__ (respond,
# provider, classify, facts) into the process.
from app.services.pii_text import (
    MARK_ADDRESS,
    # ``_redact`` rather than ``redact_customer_text``: the public verb turns
    # the lone-number guess on, which reads every "2019 - 2022" in a CV as a
    # pasted OTP. ``allow_lone_code=False`` is the same setting the shared
    # module's own ``safe_fact_value`` uses for text that is not somebody
    # talking. There is no public kwarg for it yet — see unlock 3 above.
    _redact as _redact_free_text,
)

log = logging.getLogger("quata.ai")

# QUATA role families the model scores a candidate's fit against.
ROLE_FAMILIES = [
    "Operations",
    "Customer Support",
    "Growth & Sales",
    "Marketing",
    "Finance",
    "Technology",
    "Human Resources",
]

_SYSTEM_PROMPT = (
    "You are an expert technical recruiter and talent analyst for QUATA Digital "
    "Enterprise, a Cameroon fintech/tech group. Analyse the candidate's CV "
    "objectively against the role they applied for and QUATA's role families. "
    "Be fair and evidence-based; do not invent experience. Return ONLY valid "
    "JSON matching the requested schema. All scores are integers from 0 to 100."
)

_MAX_CV_CHARS = 15000


def ai_enabled() -> bool:
    return settings.ai_enabled


class AiUnavailable(RuntimeError):
    """AI is not configured or the CV could not be read."""


def extract_cv_text(path: Path) -> str:
    """Best-effort plain-text extraction from a CV file (PDF or text)."""
    suffix = path.suffix.lower()
    text = ""
    try:
        if suffix == ".pdf":
            from pypdf import PdfReader

            reader = PdfReader(str(path))
            text = "\n".join((page.extract_text() or "") for page in reader.pages)
        elif suffix in (".txt", ".md", ".rtf"):
            text = path.read_text(errors="ignore")
    except Exception as exc:  # noqa: BLE001
        log.warning("CV text extraction failed for %s: %s", path, exc)
        text = ""
    return text.strip()[:_MAX_CV_CHARS]


# ---------------------------------------------------------------------------
# What the model is allowed to see of the candidate's CV
# ---------------------------------------------------------------------------

# Markers for the categories a CV has and a WhatsApp sentence does not. Same
# convention as ``whatsapp/ai/pii.py``: a *typed* marker, so the model can
# still reason about the document ("the header held a name") without holding
# the value, and no digits inside, so the filter is idempotent.
MARK_NAME = "[name]"
MARK_DOB = "[dob]"
MARK_HANDLE = "[handle]"

# How far into the document the name may hide. A CV puts it in the first
# visual block or not at all; scanning further starts eating body text.
_HEADER_LINES = 6
_NAME_MAX_TOKENS = 4
_NAME_MAX_CHARS = 48
# Short tokens are initials and particles ("de", "Jr"), too collision-prone to
# scrub out of the whole document.
_NAME_TOKEN_MIN_CHARS = 3

# A CV is a form, so most identifiers arrive with a label saying what they
# are. All three of these are line-anchored: "Nom:" at the start of a line is
# the candidate's name, while "Nom de l'entreprise:" is not — and the label
# itself is kept, because it tells the model what was removed.
_LABELLED_NAME = re.compile(
    r"(?im)^[ \t]*("
    r"noms?(?:\s+et\s+pr[ée]noms?)?|pr[ée]noms?|"
    r"full[ \t]?name|name|candidat[e]?|applicant"
    r")[ \t]*[:\-–][ \t]*(.+)$"
)

# ``\b``-terminated on every branch so a label cannot fire inside a longer
# word — bare ``dob`` would otherwise match "Dobermann" and swallow the rest
# of the line as a date. The dotted form is spelled out for the same reason.
_LABELLED_DOB = re.compile(
    r"(?i)\b("
    r"date\s+de\s+naissance|n[ée]e?\s+le|date\s+of\s+birth|birth\s?date|"
    r"dob|d\.o\.b"
    r")\b\.?[ \t]*[:\-–]?[ \t]*([^\n|;,]{3,32})"
)

# The address as a CV field. ``whatsapp/ai/pii.py`` already handles the
# sentence forms ("mon adresse est …", "I live at …"); a CV writes
# "Adresse : 45 rue Njo-Njo, Bonapriso". ``location``/``ville``/``city`` are
# deliberately **not** in this list — see the docstring below.
_LABELLED_ADDRESS_FIELD = re.compile(
    r"(?im)^[ \t]*("
    r"adresse|address|domicile|r[ée]sidence|residence|"
    r"b\.?[ \t]?p\.?|p\.?[ \t]?o\.?[ \t]?box"
    r")[ \t]*[:\-–][ \t]*(.+)$"
)

# A profile URL is a personal handle. The model cannot fetch any of these, so
# the path carries no capability signal at all — only identity. The host is
# kept, because "has a GitHub" is weak evidence and is not an identifier.
_PROFILE_URL = re.compile(
    r"(?i)\b((?:https?://)?(?:[a-z0-9-]+\.)?"
    r"(?:linkedin\.com|github\.com|gitlab\.com|x\.com|twitter\.com|"
    r"facebook\.com|instagram\.com|behance\.net|dribbble\.com|medium\.com|"
    r"t\.me|wa\.me)/)[^\s|,;]+"
)

# Where a header line stops being the name and starts being the rest of the
# header: a run of spaces from PDF column layout, or a visual separator.
_HEADER_SEGMENT = re.compile(r"\s{2,}|[|•·—–/]|,")

# Words that mean a header segment is a heading or a job title rather than a
# person. This is what keeps "Senior Operations Manager" — the headline role
# many CVs open with — out of the name guess. Both languages.
_NOT_A_NAME = re.compile(
    r"(?i)\b(?:cv|curriculum|vitae|r[ée]sum[ée]|resume|profil\w*|profile|"
    r"contact\w*|coordonn[ée]es|experience|exp[ée]rience|education|formation|"
    r"comp[ée]tences|skills|objectif|objective|summary|"
    r"manager|management|engineer|ing[ée]nieur|developer|d[ée]veloppeur|"
    r"analyst\w*|consultant\w*|director|directeur|officer|assistant\w*|"
    r"technicien\w*|comptable|designer|specialist\w*|sp[ée]cialiste|"
    r"intern|interne|stagiaire|chef|senior|junior|lead|responsable)\b"
)


def _looks_like_a_name(text: str) -> bool:
    """Two to four capitalised words, no digits, no heading or title wording."""
    tokens = text.split()
    if not (2 <= len(tokens) <= _NAME_MAX_TOKENS) or len(text) > _NAME_MAX_CHARS:
        return False
    if any(ch.isdigit() for ch in text) or _NOT_A_NAME.search(text):
        return False
    for token in tokens:
        core = token.strip(".'’-")
        if not core or not core[0].isupper():
            return False
        if not core.replace("-", "").replace("'", "").replace("’", "").isalpha():
            return False
    return True


def _header_name(text: str) -> str | None:
    """The candidate's own name, from where a CV always puts it: the top.

    The first segment of each of the first few non-empty lines is tested, not
    the whole line — the commonest header on earth is "MARIE NGOH | Ops
    Manager | marie@example.cm", and a whole-line test forwards that name.
    """
    seen = 0
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        seen += 1
        if seen > _HEADER_LINES:
            return None
        candidate = _HEADER_SEGMENT.split(line)[0].strip(" \t-–—:•|")
        if _looks_like_a_name(candidate):
            return candidate
    return None


def _scrub_phrase(text: str, phrase: str) -> str:
    """Remove one name wherever it recurs, however its spacing was extracted."""
    words = [re.escape(w) for w in phrase.split()]
    if not words:
        return text
    return re.sub(r"\b" + r"\s+".join(words) + r"\b", MARK_NAME, text, flags=re.I)


def redact_cv_text(text: str) -> str:
    """Strip the candidate's personal identifiers out of a CV.

    Call this on everything about to be put in a prompt. It filters the copy
    that leaves the country and nothing else: the uploaded PDF and the
    ``applications`` row still hold the real CV, the real name and the real
    contact details, under the ``careers:manage`` permission that already
    guards them. Idempotent — the markers carry no digits and match none of
    the rules — so text that passes through twice is not damaged.

    **This is not a third redactor.** Phones (every Cameroonian notation,
    including the spaced ones whose separator hole was found and closed),
    emails, card PANs, labelled CNI/NIU/passport numbers and bare 9+ digit
    runs are all delegated to ``whatsapp.ai.pii``, unchanged. Only the
    categories below are added here, because they are the ones a *document*
    has and a chat sentence does not.

    One deliberate difference from ``redact_customer_text``: the lone-number
    guess is off (``allow_lone_code=False``, the same setting
    ``pii.safe_fact_value`` uses for text that is not a customer utterance).
    A CV is four-digit years standing alone in their own segment from top to
    bottom — "Ops Manager, MTN Cameroon | 2019 - 2022" — and with the guess
    on, every employment date became ``[code]``. A document is not somebody
    pasting an OTP, and there is no OTP in a CV to protect.

    -----------------------------------------------------------------------
    Where the line falls, and why
    -----------------------------------------------------------------------

    The point of analysing a CV is to judge a candidate against a role, so
    the line is **identifies a PERSON** versus **describes a CAPABILITY**.
    Strip the employment history and the feature is worthless; strip nothing
    and we ship an identified person's file abroad.

    REDACTED — identifies the person:

    * **Name**, in the two places it is findable: a labelled field
      ("Nom et prénoms: …", "Full name: …") and the first name-shaped segment
      of the header block. Once found it is scrubbed *everywhere* in the
      document, which is what catches the per-page footer of a multi-page CV.
      For a labelled name each token is scrubbed too, since the label is
      evidence and the individual words are the name; for the header *guess*
      only the whole phrase is, so a mis-guess costs one line rather than a
      word the rest of the CV needed.
    * **Phone numbers**, including MoMo/Orange Money numbers — same rule,
      same module as WhatsApp. Nothing downstream can dial one.
    * **Email addresses.**
    * **Identity document numbers** — CNI, NIU, passport — by their label, so
      an alphanumeric CNI is caught as well as a numeric one. The label stays.
    * **Card PANs** (13–19 digits passing Luhn). Never a reason to forward one.
    * **Date of birth**, labelled, in French and English. It is a strong
      quasi-identifier and it is also how a CV screen discriminates by age,
      so removing it costs nothing the analysis is entitled to.
    * **The address as a form field** ("Adresse:", "Address:", "Domicile:",
      "BP …"), value and all.
    * **Profile URL paths** — LinkedIn, GitHub and friends. The handle is the
      person; the host is kept.

    KEPT — describes the capability, and the analysis is worthless without it:

    * **Job titles and employers** — "Operations Manager, MTN Cameroon".
    * **Dates and durations of employment**, and education years. These are
      the seniority signal; see the lone-number note above.
    * **Skills, languages, certifications, education, achievements**,
      including the numbers in them ("14 agents", "25 000 000 FCFA budget").
    * **City, region and country when they are not in an address field** —
      "Location: Douala" survives on purpose. Where a candidate can work is
      a hiring fact, not a personal identifier, and it is the reason
      ``location``/``ville``/``city`` are absent from
      ``_LABELLED_ADDRESS_FIELD``. The cost is the other direction: a bare
      city written under "Adresse:" goes with the street, because the field
      cannot be split reliably.

    -----------------------------------------------------------------------
    What STILL crosses the border after this filter
    -----------------------------------------------------------------------

    Something always does. Stated so the owner can price it, not hidden:

    * **Other people's names** — a referee, a manager named in a bullet, a
      colleague. Only the candidate's own name has a position in the document
      to key on; a third party's does not, and there is no reliable regex for
      a Cameroonian personal name (the same conclusion ``whatsapp/ai/pii.py``
      reached). Their phone and email *are* removed, being shape-detectable.
    * **The candidate's name when it is not in the header and not labelled** —
      a two-column PDF that extracts as one glued line, or a name in a
      closing signature only.
    * **An unlabelled address** — "45 rue Njo-Njo, Bonapriso" on a line of its
      own. A heuristic broad enough to catch it eats employers and schools.
    * **Nationality, gender, marital status, number of children, religion and
      place of birth** — all common on Cameroonian CVs, all unlabelled prose
      or labels not enumerated here, all still forwarded. This is the largest
      remaining category and the honest reason is scope, not safety.
    * **A person's name inside an employer or school name**, e.g. a
      "Cabinet Ngoh & Associés" the candidate is unrelated to — and, the other
      way, a candidate whose surname *is* their employer's.
    * **Everything about the person's career** — every employer, every date,
      every school, every skill. That is the feature, and it is still a
      personal-data transfer: the set of "Ops Manager at MTN Cameroon
      2019-2022, Master from Université de Douala 2013" is small enough to
      re-identify a person even with the name gone. The filter reduces the
      transfer, it does not make it anonymous, and a deployment that cannot
      accept that should leave ``OPENAI_API_KEY`` unset — which disables this
      feature entirely.
    * **A 9-or-more-digit grouped number** — an FCFA figure like
      "120 000 000" — is masked as ``[id]`` by the shared rule. Over-redaction
      rather than a leak, and left alone deliberately: closing it means
      touching the shared redactor's separator handling.

    None of this touches storage or the response. The model's answer is stored
    as it comes back; it can no longer echo the candidate's name because it
    was never given it.
    """
    value = str(text or "")
    if not value.strip():
        return value

    # 1. Labelled fields first — the label is the strongest evidence in a CV,
    #    and its value is bounded by the line it sits on.
    labelled_names = [m.group(2).strip() for m in _LABELLED_NAME.finditer(value)]
    value = _LABELLED_NAME.sub(lambda m: f"{m.group(1)}: {MARK_NAME}", value)
    value = _LABELLED_DOB.sub(lambda m: f"{m.group(1)}: {MARK_DOB}", value)
    value = _LABELLED_ADDRESS_FIELD.sub(
        lambda m: f"{m.group(1)}: {MARK_ADDRESS}", value
    )
    value = _PROFILE_URL.sub(lambda m: f"{m.group(1)}{MARK_HANDLE}", value)

    # 2. The name in the header, and then that name wherever else it recurs.
    header = _header_name(value)
    for phrase in ([header] if header else []) + labelled_names:
        value = _scrub_phrase(value, phrase)
    for phrase in labelled_names:
        for token in phrase.split():
            if len(token) >= _NAME_TOKEN_MIN_CHARS:
                value = _scrub_phrase(value, token)

    # 3. The shared free-text sweep: phones, email, card, ID, long digit runs.
    return _redact_free_text(value, after_auth_message=False, allow_lone_code=False)


def analyze_cv(cv_text: str, job_title: str) -> dict:
    """Run the CV through OpenAI and return the structured analysis dict.

    Raises ``AiUnavailable`` when the key/package is missing, or a RuntimeError
    on an API/parse failure (the caller turns these into a clean HTTP error).
    """
    from app.services.notifications import ai_events

    if not ai_enabled():
        ai_events.unavailable("AI is not configured (no OPENAI_API_KEY).")
        raise AiUnavailable("AI is not configured (no OPENAI_API_KEY).")
    if not cv_text.strip():
        # A blank CV is the applicant's file, not an AI outage — no alert.
        raise AiUnavailable("Could not read any text from the CV (is it a scanned image?).")

    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover
        ai_events.unavailable("The openai package is not installed.")
        raise AiUnavailable("The openai package is not installed.") from exc

    # Owner decision 2026-08-18 — the model runs on QUATA's own server. A CV
    # carries more personal data than anything else this platform sends to a
    # model, so a request that would leave the region is refused rather than
    # sent. `base_url=... or None` below would silently default to OpenAI.
    try:
        ai_residency.check(settings.OPENAI_BASE_URL, settings.AI_DATA_RESIDENCY)
    except ai_residency.ResidencyBreach as exc:
        ai_events.unavailable(str(exc))
        raise AiUnavailable(str(exc)) from exc

    client = OpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL or None,
        timeout=45,
    )
    user_prompt = (
        f"Role applied for: {job_title}\n"
        f"QUATA role families to score fit for: {', '.join(ROLE_FAMILIES)}\n\n"
        "Return a JSON object with EXACTLY these keys:\n"
        "- overall_score (int 0-100): fit for the applied role\n"
        "- role_matches: array of objects {\"role\": <one of the families>, "
        "\"score\": int 0-100} — one entry per family listed above\n"
        "- recommended_role (string), recommended_department (string)\n"
        "- strengths (array of short strings), weaknesses (array of short strings)\n"
        "- skills (array), soft_skills (array), languages (array), certifications (array)\n"
        "- years_experience (number), education_summary (string)\n"
        "- interview_questions (array of 5 role-tailored questions)\n"
        "- training_recommendations (array of short strings)\n"
        "- hiring_recommendation (one of: \"Strong hire\", \"Hire\", \"Maybe\", "
        "\"Consider another role\", \"Do not hire\")\n"
        "- summary (2-3 sentence overview)\n\n"
        # Filtered, never raw: this string crosses the border. See
        # ``redact_cv_text`` for what goes, what stays, and what still leaves.
        f'CV:\n"""\n{redact_cv_text(cv_text)}\n"""'
    )

    try:
        resp = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        data = json.loads(resp.choices[0].message.content or "{}")
    except Exception as exc:  # noqa: BLE001
        log.exception("OpenAI CV analysis failed")
        ai_events.api_error(
            error=f"{type(exc).__name__}: {exc}",
            model=settings.OPENAI_MODEL,
            operation="cv_analysis",
        )
        raise RuntimeError(f"AI analysis failed: {exc}") from exc
    else:
        ai_events.request_succeeded(model=settings.OPENAI_MODEL, operation="cv_analysis")

    # Light normalisation so the frontend can rely on shapes.
    try:
        data["overall_score"] = int(data.get("overall_score") or 0)
    except (TypeError, ValueError):
        data["overall_score"] = 0
    if not isinstance(data.get("role_matches"), list):
        data["role_matches"] = []
    for key in ("strengths", "weaknesses", "skills", "soft_skills", "languages",
                "certifications", "interview_questions", "training_recommendations"):
        if not isinstance(data.get(key), list):
            data[key] = []
    data["model"] = settings.OPENAI_MODEL
    return data
