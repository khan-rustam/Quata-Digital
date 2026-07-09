"""HRMS Phase 3: executive HR analytics dashboard aggregates."""
from datetime import date, timedelta


def test_hr_alerts_contracts_and_probation(client, admin_headers):
    s = client.post(
        "/api/v1/admin/staff",
        headers=admin_headers,
        json={"email": "alert.staff@example.com", "full_name": "Alert Staff", "role_slug": "staff"},
    ).json()
    soon = (date.today() + timedelta(days=10)).isoformat()
    client.patch(
        f"/api/v1/admin/staff/{s['id']}/profile",
        headers=admin_headers,
        json={"contract_expiry": soon, "probation_status": "probation"},
    )
    body = client.get("/api/v1/admin/hr-alerts", headers=admin_headers).json()
    assert any(c["id"] == s["id"] for c in body["contracts_expiring"])
    assert any(p["id"] == s["id"] for p in body["on_probation"])
    assert body["counts"]["on_probation"] >= 1


def test_hr_analytics_shape(client, admin_headers):
    r = client.get("/api/v1/admin/hr-analytics", headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()

    totals = body["totals"]
    for key in (
        "employees", "active_employees", "open_vacancies", "applicants",
        "on_leave_today", "pending_leave", "business_units", "departments",
        "new_hires_30d",
    ):
        assert key in totals, key
        assert isinstance(totals[key], int)

    # Seeded data: at least the founder admin + the 5 seeded business units.
    assert totals["employees"] >= 1
    assert totals["business_units"] >= 5

    assert isinstance(body["headcount_by_department"], list)
    assert isinstance(body["headcount_by_business_unit"], list)
    assert isinstance(body["recruitment_funnel"], list)
    for key in ("gender_distribution", "age_distribution", "tenure_distribution", "employment_type_distribution"):
        assert key in body and isinstance(body[key], list), key
    # Every employee lands in exactly one age + tenure bucket.
    assert sum(b["count"] for b in body["age_distribution"]) == totals["employees"]
    assert sum(b["count"] for b in body["tenure_distribution"]) == totals["employees"]


def test_hr_analytics_funnel_counts_real_applicants(client, admin_headers):
    # Create one applicant, then it should appear in the "new" funnel bucket.
    up = client.post(
        "/api/v1/uploads/public",
        files={"file": ("cv.pdf", b"CV", "application/pdf")},
        data={"folder": "resumes"},
    )
    job_id = client.get("/api/v1/jobs").json()[0]["id"]
    client.post(
        f"/api/v1/jobs/{job_id}/apply",
        json={"full_name": "Funnel Test", "email": "funnel.analytics@example.com", "resume_url": up.json()["url"]},
    )
    body = client.get("/api/v1/admin/hr-analytics", headers=admin_headers).json()
    new_bucket = next((f for f in body["recruitment_funnel"] if f["stage"] == "new"), None)
    assert new_bucket is not None and new_bucket["count"] >= 1
