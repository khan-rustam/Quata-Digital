"""HRMS 1E: AI CV analysis — feature-flagged, OpenAI-backed.

The OpenAI call is never made in tests; it's monkeypatched so we exercise the
endpoint wiring, storage and the disabled path without a key or network.
"""
import app.services.ai_cv as ai_cv


def _make_application(client, admin_headers, email: str) -> int:
    up = client.post(
        "/api/v1/uploads/public",
        files={"file": ("cv.pdf", b"CV text", "application/pdf")},
        data={"folder": "resumes"},
    )
    job_id = client.get("/api/v1/jobs").json()[0]["id"]
    client.post(
        f"/api/v1/jobs/{job_id}/apply",
        json={"full_name": "AI Cand", "email": email, "resume_url": up.json()["url"]},
    )
    apps = client.get("/api/v1/admin/applications/v2", headers=admin_headers).json()
    return next(a["id"] for a in apps if a["email"] == email)


def test_analyze_disabled_without_key(client, admin_headers):
    app_id = _make_application(client, admin_headers, "ai.off@example.com")
    r = client.post(f"/api/v1/admin/applications/{app_id}/analyze", headers=admin_headers)
    assert r.status_code == 400  # not configured

    detail = client.get(f"/api/v1/admin/applications/{app_id}", headers=admin_headers).json()
    assert detail["ai_available"] is False
    assert detail["ai_analysis"] is None


def test_analyze_stores_result_when_enabled(client, admin_headers, monkeypatch):
    app_id = _make_application(client, admin_headers, "ai.on@example.com")

    fake = {
        "overall_score": 87,
        "role_matches": [{"role": "Operations", "score": 90}],
        "strengths": ["Strong ops background"],
        "weaknesses": [],
        "interview_questions": ["Tell us about a process you improved."],
        "hiring_recommendation": "Hire",
        "recommended_role": "Operations",
        "summary": "Solid operator.",
        "model": "test-model",
    }
    monkeypatch.setattr(ai_cv, "ai_enabled", lambda: True)
    monkeypatch.setattr(ai_cv, "extract_cv_text", lambda path: "extracted cv text")
    monkeypatch.setattr(ai_cv, "analyze_cv", lambda text, job_title: fake)

    r = client.post(f"/api/v1/admin/applications/{app_id}/analyze", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["ai_score"] == 87

    detail = client.get(f"/api/v1/admin/applications/{app_id}", headers=admin_headers).json()
    assert detail["ai_score"] == 87
    assert detail["ai_analysis"]["hiring_recommendation"] == "Hire"
    assert detail["ai_analyzed_at"] is not None
