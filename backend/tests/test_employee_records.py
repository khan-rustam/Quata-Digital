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
