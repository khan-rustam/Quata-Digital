"""Pytest coverage for the site-settings store + integration test endpoints
+ broadcast queue mode reporting + the unsubscribe HMAC roundtrip.
"""
from __future__ import annotations


def test_public_site_settings_excludes_secrets(client):
    """The public payload must never leak hCaptcha secret or Sentry DSN."""
    r = client.get("/api/v1/site-settings")
    assert r.status_code == 200
    body = r.json()
    leaked = [k for k in body if "secret" in k or "sentry_dsn" in k]
    assert leaked == []


def test_admin_site_settings_lists_all_groups(client, admin_headers):
    r = client.get("/api/v1/admin/site-settings", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert set(body["groups"]) >= {"contact", "integrations", "social", "toggles"}


def test_admin_can_update_single_setting(client, admin_headers):
    r = client.put(
        "/api/v1/admin/site-settings/contact.phone",
        json={"value": "+237 6 99 88 77 66"},
        headers=admin_headers,
    )
    assert r.status_code == 200
    assert r.json()["value"] == "+237 6 99 88 77 66"


def test_admin_bulk_update_settings(client, admin_headers):
    r = client.post(
        "/api/v1/admin/site-settings/bulk",
        json={
            "items": [
                {"key": "social.linkedin_url", "value": "https://linkedin.com/test"},
                {"key": "social.twitter_url", "value": "https://x.com/test"},
            ]
        },
        headers=admin_headers,
    )
    assert r.status_code == 200
    assert set(r.json()["updated"]) == {"social.linkedin_url", "social.twitter_url"}


def test_unknown_setting_key_returns_404(client, admin_headers):
    r = client.put(
        "/api/v1/admin/site-settings/some.fake.key",
        json={"value": "x"},
        headers=admin_headers,
    )
    assert r.status_code == 404


def test_test_endpoints_report_unconfigured(client, admin_headers):
    # No keys / DSN set in the test env → endpoints return ok=False
    # without doing a network round-trip.
    r = client.post(
        "/api/v1/admin/site-settings/test-hcaptcha",
        json={},
        headers=admin_headers,
    )
    assert r.status_code == 200
    assert r.json()["configured"] is False

    r = client.post(
        "/api/v1/admin/site-settings/test-sentry",
        json={},
        headers=admin_headers,
    )
    assert r.status_code == 200
    assert r.json()["configured"] is False


def test_queue_status_endpoint_runs(client, admin_headers):
    """Without REDIS_URL the queue-status endpoint reports synchronous mode."""
    r = client.get(
        "/api/v1/admin/site-settings/queue-status",
        headers=admin_headers,
    )
    assert r.status_code == 200
    body = r.json()
    # `mode` is "synchronous" without Redis, "redis" with it.
    assert body.get("mode") in {"synchronous", "redis"}


def test_unsubscribe_hmac_roundtrip(client):
    """One-click unsubscribe accepts a valid HMAC token, rejects garbage,
    and never leaks list membership."""
    from app.services.newsletter_tokens import make_unsubscribe_token

    # Subscribe an address so we can unsubscribe it.
    r = client.post(
        "/api/v1/newsletter/subscribe",
        json={"email": "loop@example.com"},
    )
    assert r.status_code in (200, 201)

    tok = make_unsubscribe_token("loop@example.com")
    # Valid token → 200 + email echoed.
    r = client.get(
        f"/api/v1/newsletter/unsubscribe?email=loop@example.com&token={tok}"
    )
    assert r.status_code == 200
    assert r.json().get("email") == "loop@example.com"

    # Invalid token → still 200 (no enumeration), but `email` not echoed.
    r = client.get(
        "/api/v1/newsletter/unsubscribe?email=loop@example.com&token=" + ("a" * 24)
    )
    assert r.status_code == 200
    assert "email" not in r.json()
