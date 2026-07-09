"""HRMS 2A: employee personnel file — personal/employment/professional fields."""


def test_update_and_read_personnel_file(client, admin_headers):
    me = client.get("/api/v1/auth/me", headers=admin_headers).json()
    mgr = client.post(
        "/api/v1/admin/staff",
        headers=admin_headers,
        json={"email": "mgr.2a@example.com", "full_name": "Mgr 2A", "role_slug": "manager"},
    ).json()

    r = client.patch(
        f"/api/v1/admin/staff/{me['id']}/profile",
        headers=admin_headers,
        json={
            "gender": "Male",
            "nationality": "Cameroonian",
            "date_of_birth": "1990-01-15",
            "employment_type": "Full-time",
            "grade": "L4",
            "work_location": "Bamenda",
            "manager_id": mgr["id"],
            "date_hired": "2024-03-01",
            "probation_status": "confirmed",
            "skills": ["Python", "Leadership"],
            "languages": ["English", "French"],
            "certifications": ["PMP"],
            "emergency_contacts": [{"name": "Jane", "relationship": "Spouse", "phone": "+237600"}],
            "education": "BSc CS",
            "portfolio_url": "https://example.com",
        },
    )
    assert r.status_code == 200, r.text

    p = client.get(f"/api/v1/admin/staff/{me['id']}", headers=admin_headers).json()["profile"]
    assert p["gender"] == "Male"
    assert p["nationality"] == "Cameroonian"
    assert p["date_of_birth"] == "1990-01-15"
    assert p["skills"] == ["Python", "Leadership"]
    assert p["languages"] == ["English", "French"]
    assert p["manager_id"] == mgr["id"]
    assert p["manager_name"] == "Mgr 2A"
    assert p["emergency_contacts"][0]["name"] == "Jane"


def test_staff_directory_csv_export(client, admin_headers):
    r = client.get("/api/v1/admin/staff/export.csv", headers=admin_headers)
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    lines = r.text.splitlines()
    assert lines[0].startswith("employee_number,full_name,email,role,department")
    assert any("admin@quatadigital.com" in ln for ln in lines[1:])
    # Auth required.
    assert client.get("/api/v1/admin/staff/export.csv").status_code == 401


def test_cannot_be_own_manager(client, admin_headers):
    me = client.get("/api/v1/auth/me", headers=admin_headers).json()
    r = client.patch(
        f"/api/v1/admin/staff/{me['id']}/profile",
        headers=admin_headers,
        json={"manager_id": me["id"]},
    )
    assert r.status_code == 400
