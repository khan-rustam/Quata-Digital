def test_login_returns_token(client):
    r = client.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@quatadigital.com",
            "password": "ChangeMe!2026",
        },
    )
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_me_includes_2fa_gates(client, admin_headers):
    r = client.get("/api/v1/auth/me", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "super_admin"
    # The session-scoped admin fixture clears `must_reset_password` and
    # conftest overrides `REQUIRE_2FA_FOR_ROLES=[]` so the resulting
    # token can hit admin endpoints. We only assert that the gate
    # fields are surfaced — their exact boolean values depend on test
    # ordering and the env override.
    assert "requires_2fa" in body
    assert "has_2fa" in body
    assert "must_reset_password" in body


def test_login_with_wrong_password_401(client):
    r = client.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@quatadigital.com",
            "password": "wrong-password",
        },
    )
    assert r.status_code == 401


def test_2fa_enrol_then_verify(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    # 1. Begin enrolment — server returns secret + QR.
    r = client.post(
        "/api/v1/me/2fa/enrol",
        headers=headers,
        json={"password": "ChangeMe!2026"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    secret = body["secret"]
    assert body["otpauth_uri"].startswith("otpauth://")
    assert body["qr_data_url"].startswith("data:image/svg")

    # 2. Compute a real TOTP code from the issued secret and verify.
    import pyotp

    code = pyotp.TOTP(secret).now()
    r2 = client.post(
        "/api/v1/me/2fa/verify",
        headers=headers,
        json={"code": code},
    )
    assert r2.status_code == 200
    assert r2.json()["enabled"] is True
    assert len(r2.json()["recovery_codes"]) > 0

    # 3. /auth/me now reflects has_2fa = true.
    me = client.get("/api/v1/auth/me", headers=headers).json()
    assert me["has_2fa"] is True

    # 4. Disable 2FA at the end so other tests can still log in with the
    #    seeded admin password. Without this, every later test that uses
    #    the admin_token fixture would 401.
    r3 = client.post(
        "/api/v1/me/2fa/disable",
        headers=headers,
        json={"password": "ChangeMe!2026"},
    )
    assert r3.status_code == 200
