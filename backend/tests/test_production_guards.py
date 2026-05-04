"""Production-config guard tests.

These tests build fresh Settings instances directly rather than rely on
`get_settings()` (which is `lru_cache`d at module import) so they don't
collide with the global session settings.
"""
from app.core.config import (
    PLACEHOLDER_ADMIN_PASSWORD,
    PLACEHOLDER_SECRET_KEY,
    ProductionConfigError,
    Settings,
)


def _settings(**overrides) -> Settings:
    base = dict(
        ENVIRONMENT="production",
        SECRET_KEY=PLACEHOLDER_SECRET_KEY,
        SEED_ON_STARTUP=True,
        AUTO_CREATE_TABLES=True,
        EMAIL_BACKEND="console",
        DEFAULT_ADMIN_PASSWORD=PLACEHOLDER_ADMIN_PASSWORD,
    )
    base.update(overrides)
    # `_env_file=None` skips reading the project .env file so the test
    # controls every value.
    return Settings(_env_file=None, **base)


def test_production_with_placeholders_lists_all_problems():
    s = _settings()
    try:
        s.assert_production_safe()
    except ProductionConfigError as exc:
        msg = str(exc)
        assert "SECRET_KEY" in msg
        assert "AUTO_CREATE_TABLES" in msg
        assert "EMAIL_BACKEND" in msg
        assert "SEED_ON_STARTUP" in msg
    else:
        raise AssertionError("expected ProductionConfigError")


def test_production_with_safe_config_boots():
    s = _settings(
        SECRET_KEY="x" * 64,
        AUTO_CREATE_TABLES=False,
        SEED_ON_STARTUP=False,
        EMAIL_BACKEND="smtp",
    )
    s.assert_production_safe()  # must not raise


def test_seed_allowed_when_explicit_override_set():
    s = _settings(
        SECRET_KEY="x" * 64,
        AUTO_CREATE_TABLES=False,
        SEED_ON_STARTUP=True,
        ALLOW_PRODUCTION_SEED=True,
        DEFAULT_ADMIN_PASSWORD="A-Real-Password-2026!",
        EMAIL_BACKEND="smtp",
    )
    s.assert_production_safe()


def test_cors_strips_localhost_in_production():
    s = _settings(
        SECRET_KEY="x" * 64,
        AUTO_CREATE_TABLES=False,
        SEED_ON_STARTUP=False,
        EMAIL_BACKEND="smtp",
    )
    origins = s.cors_origins
    assert all(not o.startswith("http://localhost") for o in origins)
    assert all(not o.startswith("http://127.") for o in origins)
    assert "https://quatadigital.com" in origins


def test_dev_keeps_localhost_origins():
    s = Settings(_env_file=None, ENVIRONMENT="development")
    assert "http://localhost:3000" in s.cors_origins
