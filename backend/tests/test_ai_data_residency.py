"""Customer data does not leave Cameroon by accident.

Owner decision (2026-08-18): the AI runs on QUATA's own server.

The risk this pins is not someone deciding to send data abroad — it is
nobody deciding anything. Both AI paths build their client as::

    OpenAI(api_key=..., base_url=settings.OPENAI_BASE_URL or None)

so an unset, cleared or mistyped base URL falls back to OpenAI's servers
in the United States, silently. Restoring an older `.env`, clearing the
variable to debug a connection, or a typo in a hostname is enough. The
WhatsApp path carries customer messages; the CV path carries an
applicant's full name, address, date of birth and employment history.

The guard therefore refuses at CALL time and treats an EMPTY base URL as a
breach, because empty is exactly how the silent fallback happens.
"""

from __future__ import annotations

import pytest

from app.services import ai_residency as r


class TestWhatCountsAsOurOwnServer:
    @pytest.mark.parametrize(
        "url",
        [
            "http://localhost:11434/v1",
            "http://127.0.0.1:8000/v1",
            "http://ollama:8000/v1",  # container name
            "http://vllm:8000",  # LAN short name
            "http://10.0.0.5:8000/v1",  # private range
            "http://192.168.1.20:8000/v1",
            "http://model.internal/v1",
        ],
    )
    def test_a_self_hosted_endpoint_is_allowed(self, url: str) -> None:
        r.check(url, r.RESIDENCY_SELF_HOSTED)

    @pytest.mark.parametrize(
        "url",
        [
            "https://api.openai.com/v1",
            "https://api.anthropic.com/v1",
            # Looks like ours. Is not. A public DNS name resolves wherever it
            # resolves, and this is the mistake most likely to be made in good
            # faith by someone who believes they are pointing at our own box.
            "https://ai.quatadigital.com/v1",
        ],
    )
    def test_an_external_endpoint_is_refused(self, url: str) -> None:
        with pytest.raises(r.ResidencyBreach):
            r.check(url, r.RESIDENCY_SELF_HOSTED)

    def test_an_unset_endpoint_is_refused_because_that_is_the_silent_fallback(self) -> None:
        """The whole reason this module exists."""
        for empty in ("", "   ", None):
            with pytest.raises(r.ResidencyBreach) as exc:
                r.check(empty, r.RESIDENCY_SELF_HOSTED)
            assert "United States" in str(exc.value), (
                "the refusal must say where the data would have gone — an operator "
                "reading 'not configured' would just set a key and try again"
            )

    def test_external_is_still_possible_when_chosen_deliberately(self) -> None:
        """A guard that cannot be turned off gets removed by whoever needs it
        off. This one is a declared decision, not a wall."""
        r.check("https://api.openai.com/v1", r.RESIDENCY_EXTERNAL)
        r.check("", r.RESIDENCY_EXTERNAL)

    def test_the_default_is_the_owner_decision(self) -> None:
        """An unset residency setting must mean self-hosted, not 'anywhere'."""
        with pytest.raises(r.ResidencyBreach):
            r.check("https://api.openai.com/v1", "")


class TestTheRefusalIsSafeToShow:
    def test_the_destination_summary_never_leaks_the_url(self) -> None:
        """A base URL can carry a token in a query string, and this string goes
        into logs and the admin health screen."""
        summary = r.destination_of("https://api.openai.com/v1?api_key=sk-secret-value")
        assert "sk-secret-value" not in summary
        assert "api.openai.com" in summary


class TestBothAiPathsAreGuarded:
    """Structural, because a new AI caller is the way this protection rots."""

    def test_the_whatsapp_provider_refuses_rather_than_calling_out(self, monkeypatch) -> None:
        from app.services.whatsapp.ai import provider

        monkeypatch.setattr(provider.env_settings, "OPENAI_API_KEY", "k")
        monkeypatch.setattr(provider.env_settings, "OPENAI_BASE_URL", "https://api.openai.com/v1")
        monkeypatch.setattr(provider.env_settings, "AI_DATA_RESIDENCY", "self_hosted")

        result = provider.complete("system", "a customer's message")

        assert result.ok is False
        assert result.status == provider.STATUS_NOT_CONFIGURED
        # Degrades the AI, not the platform: the conversation goes to a human.
        assert result.detail == "residency_breach"

    def test_the_cv_path_refuses_rather_than_calling_out(self, monkeypatch) -> None:
        from app.services import ai_cv
        from app.services.notifications import ai_events

        monkeypatch.setattr(ai_cv, "ai_enabled", lambda: True)
        monkeypatch.setattr(ai_cv.settings, "OPENAI_BASE_URL", "https://api.openai.com/v1")
        monkeypatch.setattr(ai_cv.settings, "AI_DATA_RESIDENCY", "self_hosted")
        # Swallow the notification. This test is about the refusal, not about
        # publishing — and a real `ai.unavailable` event here lands inside the
        # dedupe window, so `test_notifications` later sees its own event
        # suppressed as a duplicate and fails. A test must not change what a
        # later test observes.
        monkeypatch.setattr(ai_events, "unavailable", lambda *a, **k: None)

        with pytest.raises(ai_cv.AiUnavailable):
            ai_cv.analyze_cv("Marie Ngoh, +237 690 11 22 33", "Operations Manager")
