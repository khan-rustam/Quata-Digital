import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from app.api.routes_admin import router as admin_router
from app.api.routes_admin_crud import router as admin_crud_router
from app.api.routes_admin_extra import router as admin_extra_router
from app.api.routes_auth import router as auth_router
from app.api.routes_devices import router as devices_router
from app.api.routes_public import router as public_router
from app.api.routes_media import router as media_router
from app.api.routes_pages import router as pages_router
from app.api.routes_security import router as security_router
from app.api.routes_self import router as self_router
from app.api.routes_site_settings import router as site_settings_router
from app.api.routes_uploads import router as uploads_router
from app.api.routes_ws import router as ws_router
from app.core.config import settings
from app.core.logging_config import configure_logging, configure_sentry
from app.core.rate_limit import limiter, rate_limit_handler
from app.core.security_headers import SecurityHeadersMiddleware
from app.db.session import SessionLocal, engine
from app.models import Base
from app.seeds.seed import run_seed


configure_logging()
configure_sentry()

# Refuse to boot in production with placeholder values. This must happen
# before lifespan so the failure surfaces during process start, not on the
# first request.
settings.assert_production_safe()


_startup_time = time.monotonic()


def _ensure_dev_schema_drift(engine_) -> None:
    """Lightweight SQLite-only schema patch for dev.

    `Base.metadata.create_all` adds missing tables but NOT missing columns.
    For long-lived dev SQLite files, when we add a new column we still want
    the app to boot. In production we use Alembic, so this is a no-op when
    the dialect is anything other than SQLite.
    """
    if engine_.dialect.name != "sqlite":
        return

    expected_user_columns = {
        "must_reset_password": "BOOLEAN NOT NULL DEFAULT 0",
        # Nullable so existing rows stay valid; older tokens (without `pwc`)
        # also remain accepted until the user next changes their password.
        "password_changed_at": "DATETIME",
    }

    with engine_.begin() as conn:
        existing = {
            row[1]
            for row in conn.exec_driver_sql("PRAGMA table_info(users)").fetchall()
        }
        if not existing:
            return  # table not created yet — create_all will handle it
        for col, ddl in expected_user_columns.items():
            if col not in existing:
                conn.exec_driver_sql(f"ALTER TABLE users ADD COLUMN {col} {ddl}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _startup_time
    if settings.AUTO_CREATE_TABLES:
        Base.metadata.create_all(bind=engine)
        _ensure_dev_schema_drift(engine)
    if settings.SEED_ON_STARTUP:
        with SessionLocal() as db:
            run_seed(db)
    # Always upsert the site-settings + marketing-pages catalogues so a
    # freshly migrated prod DB has them rendered for the admin even with
    # SEED_ON_STARTUP=false. Existing values + section content are preserved.
    try:
        from app.services.site_settings import seed_default_settings
        from app.services.page_content import seed_default_pages
        from app.services.page_content_seeds import seed_default_section_content
        with SessionLocal() as db:
            seed_default_settings(db)
            seed_default_pages(db)
            seed_default_section_content(db)
    except Exception:  # noqa: BLE001
        # Don't crash boot if the tables aren't ready yet — Alembic will catch up.
        pass
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    _startup_time = time.monotonic()
    yield


# Disable the interactive API explorers in production — they enumerate
# every admin endpoint (retention prune, role CRUD, broadcast, etc.) and
# leak the full schema even before auth.
_docs_enabled = not settings.is_production
app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.3.0",
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url=f"{settings.API_PREFIX}/openapi.json" if _docs_enabled else None,
    lifespan=lifespan,
)

# Rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

# Defence-in-depth response headers (CSP/HSTS/X-Frame-Options/etc).
app.add_middleware(
    SecurityHeadersMiddleware,
    csp_enforce=settings.CSP_ENFORCE,
    hsts_preload=settings.HSTS_PRELOAD,
    is_production=settings.is_production,
)

# CORS — explicit method + header lists. `allow_credentials=True` with
# wildcard methods/headers is ignored by browsers anyway, so listing them
# both makes the behaviour deterministic and stops silent failures.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Requested-With",
        "X-Device-Signature",
        "X-Device-Timestamp",
    ],
    expose_headers=["Content-Disposition"],
)

# Applicant CVs are private (boss Q1): resumes land under
# ``/uploads/<yyyy>/<mm>/resumes/...`` but must NOT be downloadable from the
# public static mount. This guard runs before the mount and 404s any public
# hit on a resume path; the only way to read a CV is the authenticated
# ``GET /admin/applications/{id}/resume`` endpoint (careers:manage).
@app.middleware("http")
async def block_public_resume_access(request, call_next):
    path = request.url.path
    if path.startswith("/uploads/") and "/resumes/" in path:
        return JSONResponse({"detail": "Not found"}, status_code=404)
    return await call_next(request)


# Static uploads — local-disk on the same VPS, no S3 needed.
Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")


@app.get("/")
def root():
    body: dict[str, object] = {
        "name": settings.PROJECT_NAME,
        "version": "0.3.0",
        "environment": settings.ENVIRONMENT,
        "api": settings.API_PREFIX,
    }
    if _docs_enabled:
        body["docs"] = "/docs"
    return body


import logging as _logging

_health_log = _logging.getLogger("quata.health")


@app.get("/health/live")
def health_live():
    """Liveness probe — does the process answer at all.

    Deliberately does **not** touch the database. A DB blip should not
    cause an orchestrator (systemd, k8s) to restart the container — only
    a true hung process should.
    """
    return {
        "status": "ok",
        "version": "0.3.0",
        "environment": settings.ENVIRONMENT,
        "uptime_seconds": round(time.monotonic() - _startup_time, 2),
    }


@app.get("/health/ready")
def health_ready():
    """Readiness probe — should traffic be routed to this instance.

    Returns 503 when the database is unavailable. The error detail goes
    to the server log; the response body says only ``degraded`` so we
    don't leak the database host/user/DSN text to an external monitor.
    """
    db_ok = False
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        db_ok = True
    except Exception as exc:  # noqa: BLE001
        _health_log.warning("readiness check failed: %s", exc)

    body = {
        "status": "ok" if db_ok else "degraded",
        "checks": {"database": "ok" if db_ok else "fail"},
    }
    return JSONResponse(body, status_code=200 if db_ok else 503)


@app.get("/health")
def health():
    """Back-compat alias — delegates to the readiness probe."""
    return health_ready()


# Order matters: more-specific routes before the generic admin list router.
app.include_router(auth_router, prefix=settings.API_PREFIX)
app.include_router(public_router, prefix=settings.API_PREFIX)
app.include_router(self_router, prefix=settings.API_PREFIX)
app.include_router(security_router, prefix=settings.API_PREFIX)
app.include_router(uploads_router, prefix=settings.API_PREFIX)
app.include_router(devices_router, prefix=settings.API_PREFIX)
app.include_router(site_settings_router, prefix=settings.API_PREFIX)
app.include_router(media_router, prefix=settings.API_PREFIX)
app.include_router(pages_router, prefix=settings.API_PREFIX)
app.include_router(admin_crud_router, prefix=settings.API_PREFIX)
app.include_router(admin_extra_router, prefix=settings.API_PREFIX)
app.include_router(admin_router, prefix=settings.API_PREFIX)

# WebSocket router — mounted at root so the path stays as /ws/messages
app.include_router(ws_router)
