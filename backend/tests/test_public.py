def test_partner_submit_records_request(client):
    r = client.post(
        "/api/v1/partners/business",
        json={
            "payload": {
                "company": "Acme Co",
                "contact": "Alice",
                "email": "alice@acme.test",
                "interest": "Merchant onboarding",
            }
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["partner_type"] == "business"
    assert body["status"] == "new"
    assert body["payload"]["company"] == "Acme Co"


def test_partner_submit_unknown_type_400(client):
    r = client.post(
        "/api/v1/partners/intergalactic",
        json={"payload": {}},
    )
    assert r.status_code == 400


def test_contact_submit(client):
    r = client.post(
        "/api/v1/contact",
        json={
            "name": "Bola",
            "email": "bola@test.com",
            "reason": "General",
            "message": "Hello",
        },
    )
    assert r.status_code == 201
    assert r.json()["ok"] is True


def test_search_finds_seeded_products(client):
    r = client.get("/api/v1/search?q=quatapay")
    assert r.status_code == 200
    body = r.json()
    assert body["totals"]["products"] >= 1
    assert any(p["slug"] == "quatapay" for p in body["results"]["products"])


def test_search_finds_seeded_blog_post(client):
    r = client.get("/api/v1/search?q=quata")
    assert r.status_code == 200
    body = r.json()
    assert body["totals"]["posts"] >= 1


def test_track_endpoint_accepts_pageview(client):
    r = client.post(
        "/api/v1/track",
        json={"path": "/about", "referrer": "https://x.com", "visitor_id": "v_test_123"},
    )
    assert r.status_code == 204
