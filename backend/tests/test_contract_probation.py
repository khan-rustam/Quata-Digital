"""HRMS: contract renewal + probation confirmation lifecycle actions."""
from datetime import date, timedelta


def _new_staff(client, admin_headers, email):
    return client.post(
        "/api/v1/admin/staff",
        headers=admin_headers,
        json={"email": email, "full_name": "Probation Pat", "role_slug": "staff"},
    ).json()


def test_confirm_probation_clears_alert(client, admin_headers):
    s = _new_staff(client, admin_headers, "prob.confirm@example.com")
    # Put them on probation with a past confirmation date (overdue).
    past = (date.today() - timedelta(days=5)).isoformat()
    client.patch(
        f"/api/v1/admin/staff/{s['id']}/profile",
        headers=admin_headers,
        json={"probation_status": "probation", "confirmation_date": past},
    )
    alerts = client.get("/api/v1/admin/hr-alerts", headers=admin_headers).json()
    assert any(p["id"] == s["id"] for p in alerts["on_probation"])

    r = client.post(f"/api/v1/admin/staff/{s['id']}/confirm-probation", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["probation_status"] == "confirmed"

    p = client.get(f"/api/v1/admin/staff/{s['id']}", headers=admin_headers).json()["profile"]
    assert p["probation_status"] == "confirmed"
    alerts2 = client.get("/api/v1/admin/hr-alerts", headers=admin_headers).json()
    assert not any(p["id"] == s["id"] for p in alerts2["on_probation"])


def test_confirm_probation_stamps_today_when_unset(client, admin_headers):
    s = _new_staff(client, admin_headers, "prob.today@example.com")
    client.patch(
        f"/api/v1/admin/staff/{s['id']}/profile",
        headers=admin_headers,
        json={"probation_status": "probation"},
    )
    r = client.post(f"/api/v1/admin/staff/{s['id']}/confirm-probation", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["confirmation_date"] == date.today().isoformat()


def test_renew_contract_updates_expiry(client, admin_headers):
    s = _new_staff(client, admin_headers, "contract.renew@example.com")
    # Expiring soon.
    soon = (date.today() + timedelta(days=10)).isoformat()
    client.patch(
        f"/api/v1/admin/staff/{s['id']}/profile",
        headers=admin_headers,
        json={"contract_expiry": soon},
    )
    new_expiry = (date.today() + timedelta(days=400)).isoformat()
    r = client.post(
        f"/api/v1/admin/staff/{s['id']}/renew-contract",
        headers=admin_headers,
        json={"contract_expiry": new_expiry},
    )
    assert r.status_code == 200, r.text
    assert r.json()["contract_expiry"] == new_expiry

    p = client.get(f"/api/v1/admin/staff/{s['id']}", headers=admin_headers).json()["profile"]
    assert p["contract_expiry"] == new_expiry


def test_lifecycle_actions_require_auth(client):
    assert client.post("/api/v1/admin/staff/1/confirm-probation").status_code == 401
    assert client.post(
        "/api/v1/admin/staff/1/renew-contract", json={"contract_expiry": "2030-01-01"}
    ).status_code == 401
