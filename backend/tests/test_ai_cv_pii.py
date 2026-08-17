"""What leaves the country when a CV is analysed (HRMS 1E).

``ai_cv.analyze_cv`` built its prompt as ``f'CV:\\n\"\"\"\\n{cv_text}\\n\"\"\"'``
and posted it to OpenAI in the United States. ``cv_text`` is the *whole*
document ``extract_cv_text`` pulled out of the uploaded PDF — the candidate's
full name, phone, email, home address, date of birth, CNI number, and their
complete employment and education history. Nothing on that path redacted
anything. It is a larger transfer of one identified person's data than the
WhatsApp support path that was fixed in ``whatsapp/ai/pii.py``.

The fix is a filter, not a switch, and the line it draws is the same line
that module drew: **what identifies a PERSON goes, what describes a
CAPABILITY stays.** A CV analysis exists to judge a candidate against a role,
so stripping the employment history would leave the feature worthless; the
tests below therefore assert *both* directions on the same document — the
identifiers are gone **and** the job titles, employers, skills, education and
years of employment are still there.

``redact_cv_text`` is not a third redactor. Phones (including the spaced
Cameroonian notations whose separator hole was found and closed), emails,
card PANs and labelled CNI/NIU/passport numbers are all delegated to
``whatsapp.ai.pii``, and ``test_spaced_cameroonian_phone_stays_closed`` is
here to fail if someone ever re-implements them locally and reintroduces
that hole. What this module adds is only what a CV has and a WhatsApp
sentence does not: a name in a document header, a labelled date of birth, a
form-style address field, and profile URLs whose path is a personal handle.

Two tests at the end pin the **residuals** — a referee's name and an
unlabelled address still cross the border. They are documented in
``redact_cv_text``'s docstring and pinned here so the leak stays visible
rather than becoming an assumed-safe.

Every test in this module was observed failing before ``redact_cv_text``
existed.
"""
from __future__ import annotations

import types

import pytest

import app.services.ai_cv as ai_cv


# A Cameroonian CV, in both languages, carrying every category the filter has
# an opinion about. Written the way pypdf hands text over: one line per visual
# line, header block first.
CV = """MARIE-CLAIRE NGOH TABI
Ops Manager | Douala, Cameroun
Tel: +237 690 11 22 33 / 677 44 55 66
Email: marie.ngoh@example.cm
Adresse: 45 rue Njo-Njo, quartier Bonapriso, Douala
Date de naissance: 12/08/1990
CNI: AB1234567
linkedin.com/in/marie-claire-ngoh

EXPERIENCE
Operations Manager, MTN Cameroon | 2019 - 2022
 - Managed a team of 14 agents; cut settlement time by 30%
Customer Support Lead, Orange Money Cameroun | 2015 - 2019

FORMATION
Master en Gestion, Universite de Douala, 2013
Baccalaureat 2008

COMPETENCES
Excel, SQL, Zendesk, gestion d'equipe, francais et anglais
"""

# What must never reach the provider.
IDENTIFIERS = [
    "MARIE-CLAIRE",
    "NGOH",
    "TABI",
    "690 11 22 33",
    "677 44 55 66",
    "marie.ngoh@example.cm",
    "AB1234567",
    "12/08/1990",
    "45 rue Njo-Njo",
    "Bonapriso",
    "marie-claire-ngoh",
]

# What must survive, or the feature has nothing left to judge.
CAPABILITY = [
    "Operations Manager",
    "MTN Cameroon",
    "2019 - 2022",
    "Customer Support Lead",
    "Orange Money Cameroun",
    "2015 - 2019",
    "Master en Gestion",
    "Universite de Douala",
    "2013",
    "Baccalaureat 2008",
    "Excel",
    "SQL",
    "Zendesk",
]


# ---------------------------------------------------------------------------
# The prompt that actually crosses the border
# ---------------------------------------------------------------------------

class _FakeOpenAI:
    """Stands in for ``openai.OpenAI`` and records what was sent to it."""

    sent: list[dict] = []

    def __init__(self, **kwargs):
        self.chat = types.SimpleNamespace(
            completions=types.SimpleNamespace(create=self._create)
        )

    def _create(self, **kwargs):
        type(self).sent.append(kwargs)
        message = types.SimpleNamespace(content='{"overall_score": 71}')
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])


@pytest.fixture()
def captured_prompt(monkeypatch):
    """Run ``analyze_cv`` against a fake provider and return the user prompt."""
    from app.services.notifications import ai_events

    _FakeOpenAI.sent = []
    monkeypatch.setattr("openai.OpenAI", _FakeOpenAI)
    monkeypatch.setattr(ai_cv, "ai_enabled", lambda: True)
    monkeypatch.setattr(ai_events, "request_succeeded", lambda **kw: None)

    ai_cv.analyze_cv(CV, "Operations Manager")
    assert len(_FakeOpenAI.sent) == 1
    messages = _FakeOpenAI.sent[0]["messages"]
    return next(m["content"] for m in messages if m["role"] == "user")


@pytest.mark.parametrize("identifier", IDENTIFIERS)
def test_prompt_carries_no_personal_identifier(captured_prompt, identifier):
    assert identifier not in captured_prompt


@pytest.mark.parametrize("kept", CAPABILITY)
def test_prompt_still_describes_the_candidates_capability(captured_prompt, kept):
    assert kept in captured_prompt


def test_prompt_is_still_a_usable_cv_prompt(captured_prompt):
    """The redaction must not eat the instructions or the CV block itself."""
    assert "Role applied for: Operations Manager" in captured_prompt
    assert 'CV:\n"""' in captured_prompt
    assert "overall_score" in captured_prompt


# ---------------------------------------------------------------------------
# The filter itself, category by category
# ---------------------------------------------------------------------------

def test_redaction_does_not_mutate_the_stored_text():
    """Only the copy that leaves is filtered. The DB keeps the real CV."""
    original = CV
    ai_cv.redact_cv_text(CV)
    assert CV == original


def test_spaced_cameroonian_phone_stays_closed():
    """The hole that was closed in the shared redactor must stay closed here.

    If this fails, someone has written a third phone regex instead of
    delegating to ``whatsapp.ai.pii``.
    """
    for shape in (
        "+237690112233",
        "+237 690 11 22 33",
        "237 6 90 11 22 33",
        "00237690112233",
        "690112233",
        "690.11.22.33",
        "690-11-22-33",
    ):
        out = ai_cv.redact_cv_text(f"Telephone: {shape}")
        assert "[phone]" in out, shape
        assert not any(ch.isdigit() for ch in out), (shape, out)


def test_email_and_card_delegate_to_the_shared_redactor():
    out = ai_cv.redact_cv_text("Email marie@example.cm — carte 4539 1488 0343 6467")
    assert "marie@example.cm" not in out
    assert "4539" not in out
    assert "[email]" in out and "[card]" in out


def test_labelled_identity_document_is_removed_but_its_label_kept():
    out = ai_cv.redact_cv_text("CNI No AB1234567 delivree a Douala")
    assert "AB1234567" not in out
    assert "CNI" in out  # the label is context, not an identifier


def test_employment_and_education_dates_survive():
    """A CV is mostly four-digit years standing alone. They are capability."""
    out = ai_cv.redact_cv_text(
        "Operations Manager, MTN Cameroon | 2019 - 2022\n"
        "Master en Gestion, 2013\n"
        "Baccalaureat 2008\n"
        "Managed 14 agents and a 25 000 000 FCFA budget\n"
    )
    for kept in ("2019 - 2022", "2013", "2008", "14 agents", "25 000 000 FCFA"):
        assert kept in out, kept
    assert "[code]" not in out


def test_header_name_is_removed_wherever_it_appears():
    out = ai_cv.redact_cv_text(
        "MARIE-CLAIRE NGOH TABI\nOps Manager\n\nEXPERIENCE\n"
        "Marie-Claire Ngoh Tabi — page 2\n"
    )
    assert "NGOH" not in out and "Ngoh" not in out
    assert "[name]" in out
    assert "Ops Manager" in out


def test_header_name_beside_contact_details_is_still_found():
    """The commonest CV header: name, then a separator, then the contacts."""
    out = ai_cv.redact_cv_text(
        "MARIE NGOH | Ops Manager | marie@example.cm | 690112233\n"
    )
    assert "NGOH" not in out
    assert "Ops Manager" in out


def test_labelled_name_scrubs_its_tokens_everywhere():
    out = ai_cv.redact_cv_text(
        "CURRICULUM VITAE\nNom et prenoms: NGOH TABI Marie\n\n"
        "PROFIL\nMarie has led operations teams since 2015.\n"
    )
    assert "NGOH" not in out and "Marie" not in out
    assert "led operations teams since 2015" in out


def test_a_job_title_in_the_header_is_not_mistaken_for_a_name():
    """The header guess must not eat the headline role."""
    out = ai_cv.redact_cv_text("Senior Operations Manager\nDouala, Cameroun\n")
    assert "Senior Operations Manager" in out


def test_date_of_birth_is_removed_in_both_languages():
    for line in (
        "Date de naissance: 12/08/1990",
        "Date de naissance : 12 aout 1990",
        "Nee le 12/08/1990 a Bafoussam",
        "Date of birth: 12 August 1990",
        "DOB 12/08/1990",
    ):
        out = ai_cv.redact_cv_text(line)
        assert "1990" not in out, line
        assert "[dob]" in out, line


def test_dob_label_does_not_fire_on_a_word_that_merely_contains_it():
    out = ai_cv.redact_cv_text("Dobermann kennel manager, 2015 - 2018")
    assert "[dob]" not in out
    assert "Dobermann kennel manager" in out


def test_form_style_address_field_is_removed():
    for line in (
        "Adresse: 45 rue Njo-Njo, quartier Bonapriso, Douala",
        "Address: BP 1234, Yaounde",
        "Domicile : Bonaberi, Douala",
    ):
        out = ai_cv.redact_cv_text(line)
        assert "[address]" in out, line
        assert "Bonapriso" not in out and "Bonaberi" not in out and "BP 1234" not in out


def test_a_city_that_is_not_an_address_field_survives():
    """Where a candidate can work is capability context, not an identifier."""
    out = ai_cv.redact_cv_text("Location: Douala, Cameroun\nOps Manager\n")
    assert "Douala" in out


def test_profile_url_keeps_the_host_and_drops_the_handle():
    out = ai_cv.redact_cv_text(
        "linkedin.com/in/marie-claire-ngoh\nhttps://github.com/marieng\n"
    )
    assert "marie-claire-ngoh" not in out and "marieng" not in out
    assert "linkedin.com" in out and "github.com" in out
    assert "[handle]" in out


def test_filter_is_idempotent():
    once = ai_cv.redact_cv_text(CV)
    assert ai_cv.redact_cv_text(once) == once


# ---------------------------------------------------------------------------
# Residuals — pinned so they stay visible
# ---------------------------------------------------------------------------

def test_residual_a_referees_name_still_crosses_the_border():
    """Documented in ``redact_cv_text``: only the candidate's own name is found.

    A referee's or a colleague's name has no position in the document to key
    on. If this ever starts passing, the docstring's residual list is stale.
    """
    out = ai_cv.redact_cv_text("MARIE NGOH\n\nReference: Jean Mbarga, +237690112233\n")
    assert "Jean Mbarga" in out


def test_residual_an_unlabelled_address_still_crosses_the_border():
    """Also documented: only the labelled form is removed, as in WhatsApp."""
    out = ai_cv.redact_cv_text("MARIE NGOH\n45 rue Njo-Njo, Bonapriso, Douala\n")
    assert "Bonapriso" in out
