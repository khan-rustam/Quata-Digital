"""HRMS: annual leave entitlement + balance (approved usage by type, this year)."""
from datetime import date


def test_leave_balance_counts_approved_annual_and_pending(client, admin_headers):
    me = client.get("/api/v1/auth/me", headers=admin_headers).json()
    year = date.today().year

    # Set the annual entitlement on the personnel file.
    r = client.patch(
        f"/api/v1/admin/staff/{me['id']}/profile",
        headers=admin_headers,
        json={"annual_leave_entitlement": 20},
    )
    assert r.status_code == 200, r.text

    # Apply 5 days of annual leave this year, then approve it.
    lr = client.post(
        "/api/v1/leave",
        headers=admin_headers,
        json={
            "leave_type": "annual",
            "start_date": f"{year}-03-01",
            "end_date": f"{year}-03-05",
            "reason": "Vacation",
        },
    )
    assert lr.status_code == 201, lr.text
    approve = client.patch(
        f"/api/v1/admin/leave/{lr.json()['id']}",
        headers=admin_headers,
        json={"status": "approved"},
    )
    assert approve.status_code == 200, approve.text

    # Apply 2 days of sick leave — left pending (should not count as used).
    client.post(
        "/api/v1/leave",
        headers=admin_headers,
        json={
            "leave_type": "sick",
            "start_date": f"{year}-04-01",
            "end_date": f"{year}-04-02",
            "reason": "Flu",
        },
    )

    bal = client.get(f"/api/v1/admin/staff/{me['id']}/leave-balance", headers=admin_headers)
    assert bal.status_code == 200, bal.text
    data = bal.json()
    assert data["year"] == year
    assert data["annual_entitlement"] == 20
    assert data["annual_used"] == 5
    assert data["annual_remaining"] == 15
    assert data["pending"] == 1
    # by_type reflects only approved requests.
    types = {t["leave_type"]: t["days"] for t in data["by_type"]}
    assert types == {"annual": 5}


def test_leave_balance_requires_auth(client):
    assert client.get("/api/v1/admin/staff/1/leave-balance").status_code == 401
