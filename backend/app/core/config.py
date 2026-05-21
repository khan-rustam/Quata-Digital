from functools import lru_cache
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# Sentinel placeholders that must never make it into production. If any of
# these survive a `production` boot, the app refuses to start.
PLACEHOLDER_SECRET_KEY = "change-me-in-production-please-make-this-very-long-and-random"
PLACEHOLDER_ADMIN_PASSWORD = "ChangeMe!2026"


class ProductionConfigError(RuntimeError):
    """Raised at startup when the production config is unsafe."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    PROJECT_NAME: str = "QUATA Digital API"
    API_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = "development"

    # SQLite by default for one-command boot. Swap to Postgres in .env for prod.
    DATABASE_URL: str = "sqlite:///./quata.db"

    SECRET_KEY: str = Field(default=PLACEHOLDER_SECRET_KEY)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Origins always allowed. In production, the localhost origins are
    # stripped automatically (see `cors_origins` below) so dev tools can't
    # talk to the prod API.
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://quatadigital.com",
        "https://www.quatadigital.com",
        "https://2025quata.quatadigital.com",
    ]

    SEED_ON_STARTUP: bool = True
    DEFAULT_ADMIN_EMAIL: str = "admin@quatadigital.com"
    DEFAULT_ADMIN_PASSWORD: str = PLACEHOLDER_ADMIN_PASSWORD
    # Explicit override required to seed in production. Without it, a
    # production boot with `SEED_ON_STARTUP=true` is treated as a config
    # error to stop us shipping with a known admin account.
    ALLOW_PRODUCTION_SEED: bool = False

    # Schema management — set to false in production once Alembic is wired.
    AUTO_CREATE_TABLES: bool = True

    # File uploads (local disk; great for VPS deployments)
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 25
    PUBLIC_BASE_URL: str = "http://localhost:8000"

    # Frontend origin used in password-reset emails etc.
    FRONTEND_URL: str = "http://localhost:3000"

    # Email — pluggable. console = print to stdout (dev). smtp = real SMTP.
    # Production primary mail provider: SMTP2GO (set SMTP_HOST=mail.smtp2go.com, SMTP_PORT=587).
    EMAIL_BACKEND: str = "console"  # console | smtp | disabled
    SMTP_HOST: str = "mail.smtp2go.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True
    EMAIL_FROM: str = "QUATA Digital <noreply@quatadigital.com>"
    EMAIL_NOTIFY_TO: str = "info@quatadigital.com"

    # Default locale + supported locales
    DEFAULT_LOCALE: str = "en"
    SUPPORTED_LOCALES: List[str] = ["en", "fr"]

    # ---------- Account security ----------
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_MINUTES: int = 15
    PASSWORD_RESET_TTL_MINUTES: int = 30
    PASSWORD_MIN_LENGTH: int = 10

    # ---------- 2FA ----------
    TOTP_ISSUER: str = "QUATA Digital"
    # Roles for which 2FA enrolment is mandatory before any admin action.
    REQUIRE_2FA_FOR_ROLES: List[str] = ["super_admin"]

    # ---------- Rate limits (slowapi-compatible strings) ----------
    RATE_LIMIT_LOGIN: str = "10/minute"
    RATE_LIMIT_PUBLIC_FORM: str = "20/minute"
    RATE_LIMIT_PASSWORD_RESET: str = "5/hour"

    # ---------- hCaptcha (boss-supplied; empty disables enforcement) ----------
    HCAPTCHA_SITE_KEY: str = ""
    HCAPTCHA_SECRET_KEY: str = ""

    # ---------- Device webhook HMAC ----------
    # Set DEVICE_REQUIRE_SIGNATURE=true to enforce HMAC signing in addition to
    # the per-device api_token. The HMAC body is "<timestamp>.<raw_body>" signed
    # with the device api_token.
    DEVICE_REQUIRE_SIGNATURE: bool = False
    DEVICE_HMAC_HEADER: str = "X-Device-Signature"
    DEVICE_HMAC_TIMESTAMP_HEADER: str = "X-Device-Timestamp"
    DEVICE_HMAC_SKEW_SECONDS: int = 300

    # ---------- Observability ----------
    SENTRY_DSN: Optional[str] = None
    SENTRY_ENV: Optional[str] = None
    LOG_FORMAT: str = "json"  # json | text

    # ---------- WebSocket ----------
    WS_PATH: str = "/ws"

    # ---------- Redis (optional; enables horizontal scaling) ----------
    # When unset, the rate limiter and WebSocket hub run in-process — safe
    # for a single uvicorn worker on one VPS. Set REDIS_URL (e.g.
    # `redis://default:password@host:6379/0`) and the rate limiter will
    # share state across workers/boxes; the WebSocket hub will also need
    # a Redis-backed implementation (see `docs/SCALING.md`).
    REDIS_URL: Optional[str] = None

    # ---------- Retention (used by `/admin/retention/prune`) ----------
    ACTIVITY_LOG_RETENTION_DAYS: int = 90
    PAGE_VIEW_RETENTION_DAYS: int = 180

    # ---------- DB connection pool (Postgres only — SQLite ignores) ----------
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_RECYCLE_SECONDS: int = 1800
    DB_POOL_PRE_PING: bool = True

    # ---------- Security headers (env toggles) ----------
    CSP_ENFORCE: bool = False  # False = Report-Only; True = enforce
    HSTS_PRELOAD: bool = False  # add `; preload` only after passing hstspreload.org

    # ---------- Trusted reverse-proxy CIDRs ----------
    # Comma-separated list of networks whose ``X-Forwarded-For`` header we
    # honour. Defaults cover localhost + the RFC1918 ranges so a typical
    # docker / single-VPS setup just works. When the immediate client is
    # *not* in this list the header is ignored and the raw socket peer is
    # used — stopping spoofed audit IPs + rate-limit bypass.
    TRUSTED_PROXIES: List[str] = [
        "127.0.0.0/8",
        "::1/128",
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "fc00::/7",
    ]

    # ---------- Upload backend (local disk vs S3) ----------
    # `local` (default) writes to UPLOAD_DIR. `s3` requires S3_BUCKET +
    # AWS creds in the env. Switching backends does not migrate existing
    # files — that's a one-shot manual sync.
    UPLOAD_BACKEND: str = "local"  # local | s3
    S3_BUCKET: Optional[str] = None
    S3_REGION: Optional[str] = None
    S3_ENDPOINT_URL: Optional[str] = None  # for R2 / MinIO compatibility
    S3_PUBLIC_URL_BASE: Optional[str] = None  # CDN domain in front of the bucket

    # ---------- Derived helpers ----------

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() in {"production", "prod"}

    @property
    def cors_origins(self) -> List[str]:
        """CORS origins with localhost entries stripped in production."""
        if not self.is_production:
            return list(self.BACKEND_CORS_ORIGINS)
        return [
            o
            for o in self.BACKEND_CORS_ORIGINS
            if not (o.startswith("http://localhost") or o.startswith("http://127."))
        ]

    def assert_production_safe(self) -> None:
        """Refuse to start when production config still uses placeholders.

        Called once at app startup. Raises `ProductionConfigError` with a
        list of every problem so the operator fixes them all in one go,
        instead of playing whack-a-mole.
        """
        if not self.is_production:
            return
        problems: List[str] = []
        if self.SECRET_KEY == PLACEHOLDER_SECRET_KEY:
            problems.append(
                "SECRET_KEY is the placeholder value. Set a 64+ char random "
                "value in the production environment."
            )
        if self.SEED_ON_STARTUP:
            if not self.ALLOW_PRODUCTION_SEED:
                problems.append(
                    "SEED_ON_STARTUP=true in production. Set "
                    "ALLOW_PRODUCTION_SEED=true if you really mean it; "
                    "otherwise set SEED_ON_STARTUP=false."
                )
            if self.DEFAULT_ADMIN_PASSWORD == PLACEHOLDER_ADMIN_PASSWORD:
                problems.append(
                    "DEFAULT_ADMIN_PASSWORD is the placeholder while "
                    "SEED_ON_STARTUP is on. Set a strong, single-use value "
                    "before seeding the production admin."
                )
        if self.AUTO_CREATE_TABLES:
            problems.append(
                "AUTO_CREATE_TABLES=true in production. Use Alembic "
                "migrations and set this to false."
            )
        if self.EMAIL_BACKEND == "console":
            problems.append(
                "EMAIL_BACKEND=console in production. Set EMAIL_BACKEND=smtp "
                "with SMTP credentials, or EMAIL_BACKEND=disabled to "
                "explicitly opt out of outbound email."
            )
        if problems:
            raise ProductionConfigError(
                "Production config refused to start:\n  - "
                + "\n  - ".join(problems)
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
