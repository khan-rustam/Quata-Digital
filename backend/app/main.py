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


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.3.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.API_PREFIX}/openapi.json",
    lifespan=lifespan,
)

# Rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

# Static uploads — local-disk on the same VPS, no S3 needed.
Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")


@app.get("/")
def root():
    return {
        "name": settings.PROJECT_NAME,
        "version": "0.3.0",
        "environment": settings.ENVIRONMENT,
        "docs": "/docs",
        "api": settings.API_PREFIX,
    }


@app.get("/health")
def health():
    """Liveness + readiness probe.

    Returns 200 only when the database accepts a `SELECT 1`. External
    monitors should treat anything other than 200 as down.
    """
    db_ok = False
    db_error: str | None = None
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        db_ok = True
    except Exception as exc:  # noqa: BLE001
        db_error = str(exc)[:200]

    body = {
        "status": "ok" if db_ok else "degraded",
        "version": "0.3.0",
        "environment": settings.ENVIRONMENT,
        "uptime_seconds": round(time.monotonic() - _startup_time, 2),
        "checks": {
            "database": "ok" if db_ok else "fail",
        },
    }
    if db_error:
        body["checks"]["database_error"] = db_error
    return JSONResponse(body, status_code=200 if db_ok else 503)


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
