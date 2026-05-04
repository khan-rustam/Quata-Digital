def test_subscribe_then_resubscribe_is_idempotent(client):
    r1 = client.post(
        "/api/v1/newsletter/subscribe",
        json={"email": "lead@example.com", "source": "test"},
    )
    assert r1.status_code == 201, r1.text
    assert r1.json()["status"] == "subscribed"

    r2 = client.post(
        "/api/v1/newsletter/subscribe",
        json={"email": "lead@example.com", "source": "test"},
    )
    assert r2.status_code == 201
    assert r2.json()["status"] == "already_subscribed"
    assert r2.json()["id"] == r1.json()["id"]


def test_unsubscribe_is_idempotent_for_unknown_email(client):
    r = client.post(
        "/api/v1/newsletter/unsubscribe",
        json={"email": "ghost@example.com"},
    )
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_unsubscribe_then_resubscribe_reactivates(client):
    client.post(
        "/api/v1/newsletter/subscribe",
        json={"email": "comeback@example.com"},
    )
    client.post(
        "/api/v1/newsletter/unsubscribe",
        json={"email": "comeback@example.com"},
    )
    r = client.post(
        "/api/v1/newsletter/subscribe",
        json={"email": "comeback@example.com"},
    )
    assert r.status_code == 201
    assert r.json()["status"] == "already_subscribed"


def test_admin_list_includes_subscriber(client, admin_headers):
    client.post(
        "/api/v1/newsletter/subscribe",
        json={"email": "visible@example.com"},
    )
    r = client.get("/api/v1/admin/newsletter", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    assert any(item["email"] == "visible@example.com" for item in body["items"])


def test_admin_export_csv(client, admin_headers):
    client.post(
        "/api/v1/newsletter/subscribe",
        json={"email": "csv@example.com"},
    )
    r = client.get(
        "/api/v1/admin/newsletter/export.csv",
        headers=admin_headers,
    )
    assert r.status_code == 200
    assert "csv@example.com" in r.text
