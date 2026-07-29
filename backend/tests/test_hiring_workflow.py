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


def test_status_change_reports_whether_the_candidate_email_went_out(
    client, admin_headers, monkeypatch
):
    """A failed send must be reported, not swallowed.

    Regression guard for a silent failure: `send_email` catches SMTP errors
    and returns False rather than raising, the notify helpers ignored that
    return, and the route's try/except therefore never fired. An offer could
    move the candidate to "hired" while the email reached nobody, and the
    admin saw an unqualified success — which is how a hire notification went
    out to no one and looked like it had been sent.
    """
    import app.services.email as email_mod

    app_id = _make_application(client, admin_headers, "silent.fail@example.com")

    # Every transport attempt fails, exactly as a bad SMTP credential would.
    monkeypatch.setattr(email_mod, "send_email", lambda **kw: False)

    r = client.patch(
        f"/api/v1/admin/applications/{app_id}",
        headers=admin_headers,
        json={"status": "hired", "start_date": "2026-08-01", "notify": True},
    )
    assert r.status_code == 200, r.text
    # The stage still moves — mail is best-effort and must not roll it back.
    assert r.json()["status"] == "hired"
    # ...but the caller is told the candidate was NOT reached.
    assert r.json()["notification_sent"] is False

    # And a working transport reports success.
    monkeypatch.setattr(email_mod, "send_email", lambda **kw: True)
    r = client.patch(
        f"/api/v1/admin/applications/{app_id}",
        headers=admin_headers,
        json={"status": "rejected", "notify": True},
    )
    assert r.status_code == 200, r.text
    assert r.json()["notification_sent"] is True


def test_status_change_without_notify_reports_no_attempt(client, admin_headers):
    """notify=false sends nothing, so there is no delivery result to report."""
    app_id = _make_application(client, admin_headers, "no.notify@example.com")
    r = client.patch(
        f"/api/v1/admin/applications/{app_id}",
        headers=admin_headers,
        json={"status": "hr_review", "notify": False},
    )
    assert r.status_code == 200, r.text
    assert r.json()["notification_sent"] is None
