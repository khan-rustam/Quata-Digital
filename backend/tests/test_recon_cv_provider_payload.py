"""RECONCILIATION PROBE — what EXACTLY did the provider get called with?

The reviewer asked for a CV containing a name, a spaced +237 phone, a CNI
number, an address and a date of birth to be sent through `analyze_cv`, and for
the argument list handed to the OpenAI client to be inspected directly — not
the return value of the redactor, and not a fixture the implementing agent
wrote. So this file substitutes the whole `openai.OpenAI` class, keeps every
kwarg of the `chat.completions.create` call, and asserts against that captured
object.

The CV below is new text, deliberately not any string used in
`tests/test_ai_cv_pii.py`.

Two directions, both mandatory:
  * nothing personal crosses the border, and
  * the analysis is still possible — job titles and employers survive, or the
    feature is dead and the redaction is a regression rather than a control.
"""

from __future__ import annotations

import pytest
from app.services import ai_cv
from app.services.notifications import ai_events

CANDIDATE_NAME = "Ngo Bakang"
CANDIDATE_FULL = "Marceline Ngo Bakang"
PHONE_SPACED = "+237 677 45 88 12"
PHONE_LOCAL = "699 20 31 44"
CNI = "108734512"
ADDRESS = "Rue 1.845, Quartier Bastos"
DOB = "14/03/1991"
EMAIL = "marceline.ngobakang@yahoo.fr"

CV = f"""Marceline Ngo Bakang
Responsable Logistique

Nom et prénoms: Marceline Ngo Bakang
Date de naissance: {DOB}
Adresse: {ADDRESS}, Yaoundé
Téléphone: {PHONE_SPACED} / {PHONE_LOCAL}
Email: {EMAIL}
CNI: {CNI}
LinkedIn: https://www.linkedin.com/in/marceline-ngo-bakang-9931

PROFIL
Responsable Logistique with 9 years in warehousing and last-mile distribution
across Cameroon.

EXPERIENCE
2019 - 2024   Responsable Logistique, Brasseries du Cameroun, Douala
              Managed a fleet of 22 trucks and a team of 31 warehouse staff.
              Cut delivery lead time from 5 days to 2 days.
2015 - 2019   Superviseur Entrepot, CAMRAIL, Yaounde
              Ran inbound goods receipt for a 12 000 m2 depot.

FORMATION
2015   Master en Logistique et Transport, Universite de Yaounde II
2012   Licence en Gestion, Universite de Douala

COMPETENCES
SAP MM, Excel avance, gestion de flotte, negociation fournisseurs
Langues: Francais (natif), Anglais (professionnel)

Marceline Ngo Bakang - CV - page 1
"""


class _CapturingOpenAI:
    """Substitute for `openai.OpenAI`. Keeps every create() kwarg verbatim."""

    calls: list[dict] = []

    def __init__(self, **kwargs):
        self.init_kwargs = kwargs
        outer = self

        class _Completions:
            @staticmethod
            def create(**kw):
                outer.calls.append(kw)

                class _Msg:
                    content = '{"overall_score": 71}'

                class _Choice:
                    message = _Msg()

                class _Resp:
                    choices = [_Choice()]

                return _Resp()

        class _Chat:
            completions = _Completions()

        self.chat = _Chat()


@pytest.fixture
def provider_call(monkeypatch):
    _CapturingOpenAI.calls = []
    monkeypatch.setattr("openai.OpenAI", _CapturingOpenAI)
    # Owner decision 2026-08-18: the model runs on QUATA's own server, and
    # `ai_residency` refuses a call that would leave the region. A capturing
    # substitute still has to declare where the model lives.
    monkeypatch.setattr(ai_cv.settings, "OPENAI_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setattr(ai_cv, "ai_enabled", lambda: True)
    monkeypatch.setattr(ai_events, "request_succeeded", lambda **kw: None)
    ai_cv.analyze_cv(CV, "Responsable Logistique")
    assert len(_CapturingOpenAI.calls) == 1, "expected exactly one provider call"
    return _CapturingOpenAI.calls[0]


@pytest.fixture
def sent_text(provider_call) -> str:
    """Every character that left the machine, system + user message alike."""
    return "\n".join(str(m.get("content", "")) for m in provider_call["messages"])


# ════════════════════════════════════════════════════════════════════
# 1. Nothing personal crossed the border
# ════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    "identifier",
    [
        pytest.param(CANDIDATE_FULL, id="full-name"),
        pytest.param(CANDIDATE_NAME, id="surname"),
        pytest.param("Marceline", id="given-name"),
        pytest.param(PHONE_SPACED, id="spaced-+237-phone"),
        pytest.param("677 45 88 12", id="phone-without-country-code"),
        pytest.param("677458812", id="phone-unspaced"),
        pytest.param(PHONE_LOCAL, id="second-phone"),
        pytest.param(CNI, id="cni-number"),
        pytest.param(EMAIL, id="email"),
        pytest.param(ADDRESS, id="address"),
        pytest.param("Rue 1.845", id="street"),
        pytest.param(DOB, id="date-of-birth"),
        pytest.param("marceline-ngo-bakang-9931", id="linkedin-handle"),
    ],
)
def test_probe_identifier_did_not_reach_the_provider(sent_text: str, identifier: str) -> None:
    assert identifier not in sent_text, (
        f"{identifier!r} was sent to OpenAI in the provider call payload"
    )


def test_probe_the_footer_recurrence_of_the_name_is_gone_too(sent_text: str) -> None:
    """The name appears three times in this CV — header, labelled field and a
    page footer. A filter that only handles the labelled field leaks the other
    two."""
    assert "Ngo Bakang" not in sent_text
    assert sent_text.count("Marceline") == 0


# ════════════════════════════════════════════════════════════════════
# 2. The analysis is still possible — the feature is not dead
# ════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    "kept",
    [
        pytest.param("Responsable Logistique", id="job-title"),
        pytest.param("Brasseries du Cameroun", id="employer-1"),
        pytest.param("CAMRAIL", id="employer-2"),
        pytest.param("Superviseur Entrepot", id="second-job-title"),
        pytest.param("2019 - 2024", id="employment-dates"),
        pytest.param("2015 - 2019", id="second-employment-dates"),
        pytest.param("Master en Logistique et Transport", id="degree"),
        pytest.param("Universite de Yaounde II", id="school"),
        pytest.param("SAP MM", id="skill"),
        pytest.param("22 trucks", id="scale-number"),
        pytest.param("31 warehouse staff", id="team-size"),
        pytest.param("Anglais (professionnel)", id="language"),
        pytest.param("Yaound", id="work-location"),
    ],
)
def test_probe_capability_signal_survived(sent_text: str, kept: str) -> None:
    assert kept in sent_text, (
        f"{kept!r} was stripped — without it the CV analysis cannot judge the "
        "candidate, and the filter has broken the feature rather than protected it"
    )


def test_probe_the_prompt_is_still_a_working_cv_prompt(provider_call) -> None:
    user = [m for m in provider_call["messages"] if m["role"] == "user"][0]["content"]
    assert "overall_score" in user
    assert "Role applied for: Responsable Logistique" in user
    assert 'CV:\n"""' in user
    assert provider_call.get("response_format") == {"type": "json_object"}


def test_probe_redaction_left_labels_behind_so_the_model_can_reason(sent_text: str) -> None:
    """A removed field should still say what it was, or the model reads a CV
    with holes in it and cannot tell an omission from a redaction."""
    for label in ("CNI", "Adresse", "Date de naissance", "Email", "LinkedIn"):
        assert label in sent_text, f"the {label!r} label was removed along with its value"


def test_probe_the_stored_cv_is_untouched() -> None:
    """Redaction is on the copy that leaves. The record keeps the real CV."""
    original = CV
    ai_cv.redact_cv_text(CV)
    assert CV == original
    assert CANDIDATE_FULL in CV
