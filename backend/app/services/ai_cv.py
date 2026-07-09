"""AI talent-intelligence engine (HRMS 1E) — OpenAI-backed CV analysis.

Disabled unless ``OPENAI_API_KEY`` is set. The openai client is imported
lazily so the app boots (and tests run) without the key or package configured.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from app.core.config import settings

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


def analyze_cv(cv_text: str, job_title: str) -> dict:
    """Run the CV through OpenAI and return the structured analysis dict.

    Raises ``AiUnavailable`` when the key/package is missing, or a RuntimeError
    on an API/parse failure (the caller turns these into a clean HTTP error).
    """
    if not ai_enabled():
        raise AiUnavailable("AI is not configured (no OPENAI_API_KEY).")
    if not cv_text.strip():
        raise AiUnavailable("Could not read any text from the CV (is it a scanned image?).")

    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover
        raise AiUnavailable("The openai package is not installed.") from exc

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
        f'CV:\n"""\n{cv_text}\n"""'
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
        raise RuntimeError(f"AI analysis failed: {exc}") from exc

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
