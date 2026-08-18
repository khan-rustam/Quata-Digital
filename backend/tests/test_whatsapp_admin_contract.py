"""The API keys the admin console's TypeScript types are written against.

The console hand-writes its types (there is no generated client in this
repo). That is fine right up until someone renames a field here and the
screen silently renders `undefined` — TypeScript cannot catch a lie about
what the server sends.

So these tests pin the *key set* of every shape the console consumes. They
are deliberately exact-match, not superset: adding a field is a change the
console should know about, and removing one is a break.

Mirror of `frontend/app/admin/qcp/shared.tsx`.
"""
from __future__ import annotations


ACCOUNT_KEYS = {
    "id", "slug", "name", "purpose", "display_phone", "api_version", "is_active",
    "health", "quality_rating", "messaging_limit", "last_checked_at", "last_error",
    "has_phone_number_id", "has_waba_id", "has_access_token", "has_app_secret",
    "has_verify_token", "configured",
    # Typed `{code, severity, message}` rows, not a free-text list: the
    # console must be able to render a `critical` differently from a merely
    # empty field, and an unset `phone_number_id` is a critical.
    "security",
}

PRODUCT_KEYS = {
    "id", "slug", "name", "description", "is_enabled", "has_api_key",
    "api_key_prefix", "allowed_purposes", "default_locale", "rate_limit_per_minute",
    "registry_version", "last_seen_at", "created_at",
    # No `has_webhook` / `webhook_url` / `has_webhook_secret`. QCP has no
    # outbound callback path, nothing ever wrote the column, and the console
    # rendered a permanent "not configured" that read as a feature waiting to
    # be switched on. Exact-match is the point of this set: if a callback path
    # is ever built, adding the keys back has to be a deliberate edit here.
}

REGISTRY_EXTRA_KEYS = {
    "routing_rules", "routing_rules_active", "templates", "messages",
    # Why this product sends nothing, in ``routing``'s own refusal codes.
    # Registry-only: the counts beside it are what a reader would otherwise
    # have to draw the conclusion from themselves, and drawing it wrongly is
    # how "the switches are all on, QCP must be broken" happens. Pinned in
    # ``test_qcp_onboarding.py``.
    "blocked_by",
}


def test_overview_keys(client, admin_headers):
    body = client.get("/api/v1/admin/qcp/overview", headers=admin_headers).json()
    assert set(body) == {
        "window_hours", "gates", "accounts", "products", "queue", "recent",
        "templates", "conversations", "failures", "denials",
    }
    assert set(body["gates"]) == {
        "env_enabled", "delivery_enabled", "any_account_active",
        "any_product_enabled", "require_signature",
    }
    assert set(body["queue"]) == {
        "queued", "oldest_queued_at", "failed", "suppressed", "total",
    }
    assert set(body["recent"]) == {"total", "sent", "queued", "failed", "suppressed"}
    assert set(body["templates"]) == {
        "total", "approved", "pending_approval", "rejected",
    }
    assert set(body["conversations"]) == {"total", "open"}
    for a in body["accounts"]:
        assert set(a) == ACCOUNT_KEYS
    for p in body["products"]:
        assert set(p) == PRODUCT_KEYS


def test_conversation_list_keys(client, admin_headers):
    body = client.get("/api/v1/admin/qcp/conversations", headers=admin_headers).json()
    assert set(body) == {"total", "page", "page_size", "items"}
    for c in body["items"]:
        assert set(c) == {
            "id", "phone_e164", "display_name", "state", "product", "account",
            "account_name", "account_purpose", "assignee_id", "unread_count",
            "locale", "last_inbound_at", "last_outbound_at",
            "service_window_expires_at", "service_window_open", "created_at",
        }


def test_conversation_detail_and_message_keys(client, admin_headers):
    listing = client.get(
        "/api/v1/admin/qcp/conversations?page_size=1", headers=admin_headers
    ).json()
    if not listing["items"]:
        # Nothing to inspect. The empty shape is pinned above; the populated
        # shape is exercised by test_whatsapp_admin_console.py's thread
        # fixture, which runs in the same session.
        return
    cid = listing["items"][0]["id"]
    body = client.get(f"/api/v1/admin/qcp/conversations/{cid}", headers=admin_headers).json()
    assert set(body) == {"conversation", "messages", "next_before_id"}
    for m in body["messages"]:
        assert set(m) == {
            "id", "message_uid", "direction", "kind", "status", "intent", "product",
            "account_purpose", "body", "variables", "to", "from", "attempts",
            "max_attempts", "error_code", "last_error", "suppressed_reason",
            "created_at", "sent_at", "delivered_at", "read_at", "failed_at",
        }


def test_template_keys(client, admin_headers):
    body = client.get("/api/v1/admin/qcp/templates", headers=admin_headers).json()
    assert set(body) == {"items", "accounts", "misbound_count"}
    for a in body["accounts"]:
        assert set(a) == {"slug", "name", "purpose", "is_active", "display_phone"}
    for t in body["items"]:
        assert set(t) == {
            "id", "name", "language", "category", "intent", "status", "account",
            "account_name", "account_purpose", "account_is_active", "product",
            "variables", "provider_template_id", "rejection_reason",
            "last_synced_at", "created_at", "misbound",
        }


def test_registry_keys(client, admin_headers):
    body = client.get("/api/v1/admin/qcp/products", headers=admin_headers).json()
    assert set(body) == {"items", "platform_templates"}
    for p in body["items"]:
        assert set(p) == PRODUCT_KEYS | REGISTRY_EXTRA_KEYS
