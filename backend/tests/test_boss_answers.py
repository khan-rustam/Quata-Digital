"""Regression tests for the launch decisions from the boss.

Covers the security-critical answers:
- Q1  applicant CVs are private (not on the public mount; auth-gated download)
- Q2  every role must enrol in 2FA (wildcard honoured)
- Q3  managers may only create/manage regular-staff roles, not other admins
"""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.routes_admin_crud import (
    _assert_can_assign_role,
    _assert_can_manage_target,
)
from app.core.config import settings


# ---------------------------------------------------------------- Q1: private CVs


def _upload_resume(client, body: bytes = b"PRIVATE CV CONTENT"):
    r = client.post(
        "/api/v1/uploads/public",
        files={"file": ("cv.pdf", body, "application/pdf")},
        data={"folder": "resumes"},
    )
    assert r.status_code == 200, r.text
    return r.json()["url"]


def test_resume_file_is_not_publicly_downloadable(client):
    url = _upload_resume(client)
    path = url[url.find("/uploads/") :]
    assert "/resumes/" in path
    # The public static mount must NOT serve resumes — the guard 404s it.
    assert client.get(path).status_code == 404


def test_resume_only_downloadable_by_authorised_admin(client, admin_headers):
    resume_url = _upload_resume(client, b"SECRET RESUME BYTES")
    job_id = client.get("/api/v1/jobs").json()[0]["id"]
    ap = client.post(
        f"/api/v1/jobs/{job_id}/apply",
        json={
            "full_name": "Priya Test",
            "email": "priya.resume@example.com",
            "resume_url": resume_url,
            "cover_letter": "Hi",
        },
    )
    assert ap.status_code == 201, ap.text

    apps = client.get("/api/v1/admin/applications/v2", headers=admin_headers).json()
    app_id = next(a["id"] for a in apps if a["email"] == "priya.resume@example.com")

    # The detail payload never leaks the raw file URL.
    detail = client.get(
        f"/api/v1/admin/applications/{app_id}", headers=admin_headers
    ).json()
    assert detail["has_resume"] is True
    assert "resume_url" not in detail

    # Anonymous download is rejected …
    assert client.get(f"/api/v1/admin/applications/{app_id}/resume").status_code == 401
    # … but an authorised reviewer gets the real bytes as an attachment.
    dl = client.get(
        f"/api/v1/admin/applications/{app_id}/resume", headers=admin_headers
    )
    assert dl.status_code == 200, dl.text
    assert dl.content == b"SECRET RESUME BYTES"
    assert "attachment" in dl.headers.get("content-disposition", "").lower()


# ---------------------------------------------------------------- Q2: 2FA for all


def test_role_requires_2fa_honours_wildcard():
    original = settings.REQUIRE_2FA_FOR_ROLES
    try:
        settings.REQUIRE_2FA_FOR_ROLES = ["*"]
        for slug in ("super_admin", "admin", "manager", "staff", "intern", "contractor"):
            assert settings.role_requires_2fa(slug) is True
        settings.REQUIRE_2FA_FOR_ROLES = ["super_admin"]
        assert settings.role_requires_2fa("super_admin") is True
        assert settings.role_requires_2fa("staff") is False
    finally:
        settings.REQUIRE_2FA_FOR_ROLES = original


# ---------------------------------------------------------------- Q3: manager scope


def _role(slug, perms):
    return SimpleNamespace(
        slug=slug, permissions=[SimpleNamespace(permission=p) for p in perms]
    )


def _user(uid, role):
    return SimpleNamespace(id=uid, role=role)


_SUPER = _role("super_admin", ["*"])
_ADMIN = _role(
    "admin",
    ["content:manage", "partners:manage", "careers:manage", "staff:manage",
     "rbac:manage", "analytics:view"],
)
_MANAGER = _role(
    "manager", ["partners:manage", "careers:manage", "staff:manage", "analytics:view"]
)
_STAFF = _role("staff", [])


def test_manager_can_assign_and_manage_regular_staff():
    mgr = _user(2, _MANAGER)
    # Regular staff carries no permissions — a manager may create/manage it.
    _assert_can_assign_role(mgr, _STAFF)
    _assert_can_manage_target(mgr, _user(9, _STAFF))


def test_manager_cannot_touch_privileged_accounts():
    mgr = _user(2, _MANAGER)
    # Assigning another management role is blocked (no rbac:manage).
    with pytest.raises(HTTPException) as e1:
        _assert_can_assign_role(mgr, _MANAGER)
    assert e1.value.status_code == 403
    # Managing another manager/admin is blocked too.
    with pytest.raises(HTTPException) as e2:
        _assert_can_manage_target(mgr, _user(3, _MANAGER))
    assert e2.value.status_code == 403
    with pytest.raises(HTTPException):
        _assert_can_assign_role(mgr, _SUPER)


def test_admin_can_still_manage_management_roles():
    admin = _user(1, _ADMIN)
    # Admin holds rbac:manage, so it may assign/manage a manager account.
    _assert_can_assign_role(admin, _MANAGER)
    _assert_can_manage_target(admin, _user(2, _MANAGER))
    # …but still cannot mint a super_admin (subset guard).
    with pytest.raises(HTTPException):
        _assert_can_assign_role(admin, _SUPER)
