"""HRMS 2B: employee identity — auto-generated, unique, sequential numbers."""
import re

_FMT = re.compile(r"^QDE-\d{4}-\d{6}$")


def test_seeded_admin_has_employee_number(client, admin_headers):
    me = client.get("/api/v1/auth/me", headers=admin_headers).json()
    detail = client.get(f"/api/v1/admin/staff/{me['id']}", headers=admin_headers).json()
    num = detail["profile"]["employee_number"]
    assert num and _FMT.match(num), num
    assert detail["profile"]["verification_code"]


def test_create_staff_assigns_employee_number(client, admin_headers):
    r = client.post(
        "/api/v1/admin/staff",
        headers=admin_headers,
        json={"email": "id.test@example.com", "full_name": "ID Test", "role_slug": "staff"},
    )
    assert r.status_code == 201, r.text
    assert _FMT.match(r.json()["employee_number"] or ""), r.json()

    lst = client.get("/api/v1/admin/staff", headers=admin_headers).json()
    row = next(s for s in lst if s["email"] == "id.test@example.com")
    assert row["employee_number"] == r.json()["employee_number"]


def test_employee_numbers_unique_and_sequential(client, admin_headers):
    nums = []
    for i in range(3):
        r = client.post(
            "/api/v1/admin/staff",
            headers=admin_headers,
            json={"email": f"seq{i}.test@example.com", "full_name": f"Seq {i}", "role_slug": "staff"},
        )
        assert r.status_code == 201, r.text
        nums.append(r.json()["employee_number"])
    assert len(set(nums)) == 3
    seqs = [int(n.rsplit("-", 1)[-1]) for n in nums]
    assert seqs == sorted(seqs) and seqs[-1] - seqs[0] == 2


def test_public_employee_verification(client, admin_headers):
    me = client.get("/api/v1/auth/me", headers=admin_headers).json()
    detail = client.get(f"/api/v1/admin/staff/{me['id']}", headers=admin_headers).json()
    code = detail["profile"]["verification_code"]
    assert code

    r = client.get(f"/api/v1/verify/{code}")  # public, no auth
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["verified"] is True
    assert body["employee_number"]
    # No PII leaks through the public verification.
    assert "email" not in body and "phone" not in body

    assert client.get("/api/v1/verify/does-not-exist").status_code == 404


def test_id_card_renders_png_and_pdf(client, admin_headers):
    me = client.get("/api/v1/auth/me", headers=admin_headers).json()
    png = client.get(f"/api/v1/admin/staff/{me['id']}/id-card", headers=admin_headers)
    assert png.status_code == 200, png.text
    assert png.headers["content-type"] == "image/png"
    assert png.content[:8] == b"\x89PNG\r\n\x1a\n"

    pdf = client.get(f"/api/v1/admin/staff/{me['id']}/id-card?format=pdf", headers=admin_headers)
    assert pdf.status_code == 200
    assert pdf.content[:5] == b"%PDF-"

    # Auth required.
    assert client.get(f"/api/v1/admin/staff/{me['id']}/id-card").status_code == 401


def test_generate_identity_is_idempotent(client, admin_headers):
    me = client.get("/api/v1/auth/me", headers=admin_headers).json()
    r = client.post(f"/api/v1/admin/staff/{me['id']}/identity", headers=admin_headers)
    assert r.status_code == 201
    num = r.json()["employee_number"]
    # Never overwrites an existing number.
    r2 = client.post(f"/api/v1/admin/staff/{me['id']}/identity", headers=admin_headers)
    assert r2.json()["employee_number"] == num
