"""HRMS payroll: payslip PDF generation from a salary record."""


def _staff(client, admin_headers, email):
    return client.post(
        "/api/v1/admin/staff",
        headers=admin_headers,
        json={"email": email, "full_name": "Payslip Pam", "role_slug": "staff"},
    ).json()


def test_payslip_pdf_download(client, admin_headers):
    s = _staff(client, admin_headers, "payslip.pam@example.com")
    rec = client.post(
        f"/api/v1/admin/staff/{s['id']}/salary",
        headers=admin_headers,
        json={
            "effective_date": "2026-01-31",
            "currency": "XAF",
            "basic_salary": 500000,
            "allowances": 50000,
            "bonus": 25000,
            "tax": 40000,
            "pension": 15000,
            "payment_method": "bank",
        },
    )
    assert rec.status_code == 201, rec.text
    record_id = rec.json()["id"]

    r = client.get(
        f"/api/v1/admin/staff/{s['id']}/salary/{record_id}/payslip.pdf",
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert "attachment" in r.headers["content-disposition"]
    assert r.content[:5] == b"%PDF-"
    assert len(r.content) > 1000


def test_payslip_missing_record_404(client, admin_headers):
    s = _staff(client, admin_headers, "payslip.none@example.com")
    r = client.get(
        f"/api/v1/admin/staff/{s['id']}/salary/999999/payslip.pdf",
        headers=admin_headers,
    )
    assert r.status_code == 404


def test_payslip_requires_payroll_permission(client):
    # No auth at all → rejected (payroll is rbac:manage-gated).
    assert client.get("/api/v1/admin/staff/1/salary/1/payslip.pdf").status_code == 401
