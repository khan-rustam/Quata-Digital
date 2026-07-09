"""Employee self-service portal: GET /me/workspace."""
from datetime import date


def test_workspace_returns_own_profile_leave_and_attendance(client, admin_headers):
    me = client.get("/api/v1/auth/me", headers=admin_headers).json()
    year = date.today().year

    # Apply for leave so it shows up in the workspace.
    client.post(
        "/api/v1/leave",
        headers=admin_headers,
        json={
            "leave_type": "annual",
            "start_date": f"{year}-06-01",
            "end_date": f"{year}-06-03",
            "reason": "Trip",
        },
    )
    # Check in so attendance reflects it.
    client.post("/api/v1/attendance/in", headers=admin_headers, json={"source": "web"})

    r = client.get("/api/v1/me/workspace", headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["profile"]["id"] == me["id"]
    assert body["profile"]["email"] == me["email"]
    assert body["leave_balance"]["year"] == year
    assert body["leave_balance"]["annual_entitlement"] >= 0
    assert any(lr["leave_type"] == "annual" for lr in body["leave_requests"])
    assert body["attendance"]["present"] >= 1
    # Checked in and not out yet.
    assert body["checked_in"] is True
    assert body["checked_in_at"] is not None


def test_workspace_requires_auth(client):
    assert client.get("/api/v1/me/workspace").status_code == 401
