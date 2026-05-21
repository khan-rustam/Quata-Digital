"""Shared test fixtures.

We deliberately use ONE SQLite test DB for the whole pytest session. Trying
to swap the SQLAlchemy engine between tests fights the module-level engine
singleton and causes flaky `OperationalError: no such table` failures.

Tests should use unique data (random emails, fresh slugs) to stay isolated
from each other. The few mutating tests (soft-delete, 2FA enrol) restore
their own state.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# IMPORTANT: this env-var setup must run BEFORE `app.core.config`,
# `app.db.session`, or `app.main` are imported anywhere. Pytest loads
# conftest.py before any test module, so this is the right place.
_FD, _DB_PATH = tempfile.mkstemp(suffix=".db", prefix="quata_pytest_")
os.close(_FD)
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"
os.environ["SEED_ON_STARTUP"] = "true"
os.environ["AUTO_CREATE_TABLES"] = "true"
os.environ["EMAIL_BACKEND"] = "console"
os.environ.setdefault("ENVIRONMENT", "development")
# Strong test-only secret so production guards don't fire when tests
# touch them.
os.environ.setdefault("SECRET_KEY", "test-secret-" + "x" * 56)
# Disable the "super_admin must have TOTP enrolled" gate for tests so
# the session-scoped admin token can reach admin endpoints. The 2FA
# enrol/verify flow is still covered explicitly by
# ``test_2fa_enrol_then_verify``.
os.environ.setdefault("REQUIRE_2FA_FOR_ROLES", "[]")


def pytest_sessionfinish(session, exitstatus):
    try:
        os.unlink(_DB_PATH)
    except OSError:
        pass


@pytest.fixture(scope="session")
def app_instance():
    from app.main import app

    return app


@pytest.fixture
def client(app_instance):
    """Per-test TestClient. Lifespan runs once at first use."""
    from fastapi.testclient import TestClient

    with TestClient(app_instance) as c:
        yield c


@pytest.fixture(scope="session")
def admin_token(app_instance):
    """One login per session — JWTs are valid for 7 days so the same token
    works across the whole pytest run. Avoids hitting the login rate-limit
    (10/minute per IP) in suites with many fixtures.

    Production seeds the super-admin with ``must_reset_password=True`` so
    the boss is forced through the reset flow on first login. That same
    flag now triggers a 403 from every non-lenient admin endpoint (see
    ``get_current_user`` in ``app/api/deps.py``). For tests we clear it
    before issuing the token so the rest of the suite can hit admin
    routes normally. The reset flow itself is covered by
    ``test_auth_and_2fa``.
    """
    from fastapi.testclient import TestClient
    from datetime import datetime, timezone
    from app.db.session import SessionLocal
    from app.models import User

    # Disable the "must reset password" gate on the seeded admin so
    # session-scoped admin requests aren't blocked. Stamp
    # password_changed_at so the resulting JWT's `pwc` claim matches
    # what the auth layer expects to see on subsequent requests.
    with SessionLocal() as db:
        admin = (
            db.query(User)
            .filter(User.email == "admin@quatadigital.com")
            .first()
        )
        if admin is not None:
            admin.must_reset_password = False
            admin.password_changed_at = datetime.now(timezone.utc)
            db.commit()

    with TestClient(app_instance) as c:
        r = c.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@quatadigital.com",
                "password": "ChangeMe!2026",
            },
        )
        if r.status_code != 200:
            raise AssertionError(f"login failed: {r.status_code} {r.text}")
        return r.json()["access_token"]


@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}
