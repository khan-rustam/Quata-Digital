"""HRMS 2G: employee records — performance reviews (+ training, assets)."""


def test_performance_reviews(client, admin_headers):
    me = client.get("/api/v1/auth/me", headers=admin_headers).json()
    r = client.post(
        f"/api/v1/admin/staff/{me['id']}/reviews",
        headers=admin_headers,
        json={"period": "2026 H1", "rating": 4, "strengths": "Great ops", "goals": "Lead a project"},
    )
    assert r.status_code == 201, r.text
    rid = r.json()["id"]

    lst = client.get(f"/api/v1/admin/staff/{me['id']}/reviews", headers=admin_headers).json()
    row = next(x for x in lst if x["id"] == rid)
    assert row["rating"] == 4
    assert row["period"] == "2026 H1"
    assert row["reviewer_name"]  # defaults to the current admin

    assert client.delete(
        f"/api/v1/admin/staff/{me['id']}/reviews/{rid}", headers=admin_headers
    ).status_code == 204


def test_training_records(client, admin_headers):
    me = client.get("/api/v1/auth/me", headers=admin_headers).json()
    r = client.post(
        f"/api/v1/admin/staff/{me['id']}/training",
        headers=admin_headers,
        json={"title": "AML basics", "training_type": "compliance", "status": "completed", "completed_on": "2026-02-01"},
    )
    assert r.status_code == 201, r.text
    tid = r.json()["id"]
    lst = client.get(f"/api/v1/admin/staff/{me['id']}/training", headers=admin_headers).json()
    assert any(x["id"] == tid and x["title"] == "AML basics" for x in lst)
    assert client.delete(
        f"/api/v1/admin/staff/{me['id']}/training/{tid}", headers=admin_headers
    ).status_code == 204
