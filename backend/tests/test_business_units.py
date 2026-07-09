"""HRMS slice 1F: business units + enterprise department fields."""


def test_business_unit_crud(client, admin_headers):
    r = client.post(
        "/api/v1/admin/business-units",
        headers=admin_headers,
        json={"slug": "test-bu", "name": "Test BU", "description": "x"},
    )
    assert r.status_code == 201, r.text
    bu_id = r.json()["id"]

    lst = client.get("/api/v1/admin/business-units", headers=admin_headers).json()
    assert any(b["id"] == bu_id for b in lst)
    # Seeded units are present too.
    assert any(b["slug"] == "quatapay" for b in lst)

    r = client.put(
        f"/api/v1/admin/business-units/{bu_id}",
        headers=admin_headers,
        json={"name": "Test BU 2"},
    )
    assert r.status_code == 200 and r.json()["name"] == "Test BU 2"

    assert (
        client.delete(f"/api/v1/admin/business-units/{bu_id}", headers=admin_headers).status_code
        == 204
    )


def test_department_enterprise_fields(client, admin_headers):
    bu = client.post(
        "/api/v1/admin/business-units",
        headers=admin_headers,
        json={"slug": "dept-bu", "name": "Dept BU"},
    ).json()

    r = client.post(
        "/api/v1/admin/departments",
        headers=admin_headers,
        json={
            "slug": "test-ent-dept",
            "name": "Test Enterprise Dept",
            "business_unit_id": bu["id"],
            "objectives": "Ship the platform",
            "kpis": "Uptime\nCSAT",
            "budget": 25_000_000,
            "max_headcount": 12,
            "office_location": "Bamenda",
        },
    )
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["business_unit_id"] == bu["id"]
    assert d["business_unit_name"] == "Dept BU"
    assert d["max_headcount"] == 12
    assert d["budget"] == 25_000_000
    assert d["objectives"] == "Ship the platform"

    lst = client.get("/api/v1/admin/departments", headers=admin_headers).json()
    row = next(x for x in lst if x["id"] == d["id"])
    assert row["business_unit_name"] == "Dept BU"
    assert row["office_location"] == "Bamenda"
