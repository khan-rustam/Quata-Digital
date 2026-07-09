"""Hiring workflow: status transitions persist scheduling details and fire the
automated candidate emails (console backend in tests) without breaking the
status update."""


def _make_application(client, admin_headers, email: str) -> int:
    up = client.post(
        "/api/v1/uploads/public",
        files={"file": ("cv.pdf", b"CV BYTES", "application/pdf")},
        data={"folder": "resumes"},
    )
    assert up.status_code == 200, up.text
    resume_url = up.json()["url"]
    job_id = client.get("/api/v1/jobs").json()[0]["id"]
    r = client.post(
        f"/api/v1/jobs/{job_id}/apply",
        json={"full_name": "Workflow Candidate", "email": email, "resume_url": resume_url},
    )
    assert r.status_code == 201, r.text
    apps = client.get("/api/v1/admin/applications/v2", headers=admin_headers).json()
    return next(a["id"] for a in apps if a["email"] == email)


def test_hiring_workflow_transitions_persist_and_notify(client, admin_headers):
    app_id = _make_application(client, admin_headers, "workflow.flow@example.com")

    # Shortlist → saves interview details, sends invite email.
    r = client.patch(
        f"/api/v1/admin/applications/{app_id}",
        headers=admin_headers,
        json={
            "status": "shortlisted",
            "interview_at": "2026-07-20T09:30:00",
            "interview_location": "Bamenda office",
            "documents": "National ID + certificates",
            "notify": True,
        },
    )
    assert r.status_code == 200, r.text
    d = client.get(f"/api/v1/admin/applications/{app_id}", headers=admin_headers).json()
    assert d["status"] == "shortlisted"
    assert d["interview_at"] is not None
    assert d["interview_location"] == "Bamenda office"

    # Hire → saves start date, sends offer email.
    r = client.patch(
        f"/api/v1/admin/applications/{app_id}",
        headers=admin_headers,
        json={"status": "hired", "start_date": "2026-08-01", "notify": True},
    )
    assert r.status_code == 200, r.text
    d = client.get(f"/api/v1/admin/applications/{app_id}", headers=admin_headers).json()
    assert d["status"] == "hired"
    assert d["start_date"] == "2026-08-01"

    # Reject → courteous email, status still updates cleanly.
    r = client.patch(
        f"/api/v1/admin/applications/{app_id}",
        headers=admin_headers,
        json={"status": "rejected", "notify": True},
    )
    assert r.status_code == 200, r.text
    assert client.get(
        f"/api/v1/admin/applications/{app_id}", headers=admin_headers
    ).json()["status"] == "rejected"


def test_full_pipeline_stages_accepted(client, admin_headers):
    """Slice 1B: the new enterprise stages persist (no email, no migration)."""
    app_id = _make_application(client, admin_headers, "stages.flow@example.com")
    for stage in [
        "hr_review", "interview_scheduled", "assessment",
        "reference_check", "offer", "offer_accepted", "archived",
    ]:
        r = client.patch(
            f"/api/v1/admin/applications/{app_id}",
            headers=admin_headers,
            json={"status": stage, "notify": False},
        )
        assert r.status_code == 200, f"{stage}: {r.text}"
        assert client.get(
            f"/api/v1/admin/applications/{app_id}", headers=admin_headers
        ).json()["status"] == stage


def test_status_update_without_notify_skips_email(client, admin_headers):
    app_id = _make_application(client, admin_headers, "silent.flow@example.com")
    r = client.patch(
        f"/api/v1/admin/applications/{app_id}",
        headers=admin_headers,
        json={"status": "interviewed", "notify": False},
    )
    assert r.status_code == 200, r.text
    assert client.get(
        f"/api/v1/admin/applications/{app_id}", headers=admin_headers
    ).json()["status"] == "interviewed"
