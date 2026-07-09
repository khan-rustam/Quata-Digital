"""HRMS: per-employee attendance summary (this-month rollup)."""


def test_attendance_summary_reflects_checkin(client, admin_headers):
    me = client.get("/api/v1/auth/me", headers=admin_headers).json()

    # Empty to start.
    s0 = client.get(f"/api/v1/admin/staff/{me['id']}/attendance-summary", headers=admin_headers)
    assert s0.status_code == 200, s0.text
    assert s0.json()["present"] == 0
    assert s0.json()["days_logged"] == 0

    # Check in, then out — one present day this month.
    ci = client.post("/api/v1/attendance/in", headers=admin_headers, json={"source": "web"})
    assert ci.status_code == 200, ci.text
    client.post("/api/v1/attendance/out", headers=admin_headers, json={"source": "web"})

    s = client.get(f"/api/v1/admin/staff/{me['id']}/attendance-summary", headers=admin_headers).json()
    assert s["present"] == 1
    assert s["days_logged"] == 1
    assert s["worked_hours"] >= 0
    assert s["avg_check_in"] is not None
    assert len(s["recent"]) == 1
    assert s["recent"][0]["status"] == "present"
    assert s["recent"][0]["check_out"] is not None


def test_attendance_summary_requires_auth(client):
    assert client.get("/api/v1/admin/staff/1/attendance-summary").status_code == 401
