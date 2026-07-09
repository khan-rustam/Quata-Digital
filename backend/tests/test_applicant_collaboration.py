"""HRMS slice 1A: assigned HR officer, internal notes, and activity timeline
on an applicant."""


def _make_application(client, admin_headers, email: str) -> int:
    up = client.post(
        "/api/v1/uploads/public",
        files={"file": ("cv.pdf", b"CV", "application/pdf")},
        data={"folder": "resumes"},
    )
    resume_url = up.json()["url"]
    job_id = client.get("/api/v1/jobs").json()[0]["id"]
    client.post(
        f"/api/v1/jobs/{job_id}/apply",
        json={"full_name": "Collab Candidate", "email": email, "resume_url": resume_url},
    )
    apps = client.get("/api/v1/admin/applications/v2", headers=admin_headers).json()
    return next(a["id"] for a in apps if a["email"] == email)


def _admin_id(client, admin_headers) -> int:
    return client.get("/api/v1/auth/me", headers=admin_headers).json()["id"]


def test_assign_hr_officer(client, admin_headers):
    app_id = _make_application(client, admin_headers, "assign.collab@example.com")
    admin_id = _admin_id(client, admin_headers)

    r = client.patch(
        f"/api/v1/admin/applications/{app_id}/assignment",
        headers=admin_headers,
        json={"assigned_hr_id": admin_id},
    )
    assert r.status_code == 200, r.text

    detail = client.get(f"/api/v1/admin/applications/{app_id}", headers=admin_headers).json()
    assert detail["assigned_hr_id"] == admin_id
    assert detail["assigned_hr_name"]

    # Unassign clears it.
    client.patch(
        f"/api/v1/admin/applications/{app_id}/assignment",
        headers=admin_headers,
        json={"assigned_hr_id": None},
    )
    detail = client.get(f"/api/v1/admin/applications/{app_id}", headers=admin_headers).json()
    assert detail["assigned_hr_id"] is None


def test_notes_and_timeline(client, admin_headers):
    app_id = _make_application(client, admin_headers, "notes.collab@example.com")

    # Empty to start.
    assert client.get(
        f"/api/v1/admin/applications/{app_id}/notes", headers=admin_headers
    ).json() == []

    r = client.post(
        f"/api/v1/admin/applications/{app_id}/notes",
        headers=admin_headers,
        json={"body": "Strong communicator, follow up on references."},
    )
    assert r.status_code == 201, r.text
    assert r.json()["author_name"]

    notes = client.get(
        f"/api/v1/admin/applications/{app_id}/notes", headers=admin_headers
    ).json()
    assert len(notes) == 1
    assert "Strong communicator" in notes[0]["body"]

    # Timeline includes the note + the synthesised submission event.
    timeline = client.get(
        f"/api/v1/admin/applications/{app_id}/timeline", headers=admin_headers
    ).json()
    actions = {ev["action"] for ev in timeline}
    assert "note" in actions
    assert "applied" in actions


def test_assign_unknown_staff_rejected(client, admin_headers):
    app_id = _make_application(client, admin_headers, "badassign.collab@example.com")
    r = client.patch(
        f"/api/v1/admin/applications/{app_id}/assignment",
        headers=admin_headers,
        json={"assigned_hr_id": 999999},
    )
    assert r.status_code == 400
