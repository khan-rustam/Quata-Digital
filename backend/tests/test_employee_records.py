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


def test_assets(client, admin_headers):
    me = client.get("/api/v1/auth/me", headers=admin_headers).json()
    r = client.post(
        f"/api/v1/admin/staff/{me['id']}/assets",
        headers=admin_headers,
        json={"asset_type": "laptop", "name": "Dell Latitude", "serial": "SN123", "assigned_on": "2026-01-10"},
    )
    assert r.status_code == 201, r.text
    aid = r.json()["id"]
    lst = client.get(f"/api/v1/admin/staff/{me['id']}/assets", headers=admin_headers).json()
    assert any(x["id"] == aid and x["asset_type"] == "laptop" and x["serial"] == "SN123" for x in lst)

    # Unknown asset type is rejected by the schema.
    bad = client.post(
        f"/api/v1/admin/staff/{me['id']}/assets",
        headers=admin_headers,
        json={"asset_type": "spaceship", "name": "x"},
    )
    assert bad.status_code == 422

    assert client.delete(
        f"/api/v1/admin/staff/{me['id']}/assets/{aid}", headers=admin_headers
    ).status_code == 204


def test_disciplinary(client, admin_headers):
    me = client.get("/api/v1/auth/me", headers=admin_headers).json()
    r = client.post(
        f"/api/v1/admin/staff/{me['id']}/disciplinary",
        headers=admin_headers,
        json={"action_type": "written_warning", "summary": "Repeated lateness", "action_date": "2026-03-01"},
    )
    assert r.status_code == 201, r.text
    did = r.json()["id"]
    lst = client.get(f"/api/v1/admin/staff/{me['id']}/disciplinary", headers=admin_headers).json()
    row = next(x for x in lst if x["id"] == did)
    assert row["action_type"] == "written_warning" and row["issued_by"]
    assert client.delete(
        f"/api/v1/admin/staff/{me['id']}/disciplinary/{did}", headers=admin_headers
    ).status_code == 204


def test_offboard_and_reactivate(client, admin_headers):
    s = client.post(
        "/api/v1/admin/staff",
        headers=admin_headers,
        json={"email": "exit.staff@example.com", "full_name": "Exit Staff", "role_slug": "staff"},
    ).json()
    r = client.post(
        f"/api/v1/admin/staff/{s['id']}/exit",
        headers=admin_headers,
        json={"exit_type": "resignation", "exit_date": "2026-06-30", "rehire_eligible": True, "assets_returned": True},
    )
    assert r.status_code == 200, r.text

    prof = client.get(f"/api/v1/admin/staff/{s['id']}", headers=admin_headers).json()["profile"]
    assert prof["status"] == "exited"
    ex = client.get(f"/api/v1/admin/staff/{s['id']}/exit", headers=admin_headers).json()
    assert ex["exit_type"] == "resignation" and ex["assets_returned"] is True

    assert client.delete(f"/api/v1/admin/staff/{s['id']}/exit", headers=admin_headers).status_code == 204
    prof = client.get(f"/api/v1/admin/staff/{s['id']}", headers=admin_headers).json()["profile"]
    assert prof["status"] == "active"


def test_cannot_offboard_self(client, admin_headers):
    me = client.get("/api/v1/auth/me", headers=admin_headers).json()
    r = client.post(
        f"/api/v1/admin/staff/{me['id']}/exit",
        headers=admin_headers,
        json={"exit_type": "resignation"},
    )
    assert r.status_code == 400
