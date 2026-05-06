"""Structured logging + Sentry."""
import logging
import sys

from app.core.config import settings


def configure_logging() -> None:
    root = logging.getLogger()
    root.handlers = []

    handler = logging.StreamHandler(sys.stdout)

    if settings.LOG_FORMAT == "json":
        JsonFormatter = None
        try:
            from pythonjsonlogger.json import JsonFormatter as JF  # type: ignore
            JsonFormatter = JF
        except ImportError:
            try:
                from pythonjsonlogger.jsonlogger import JsonFormatter as JF  # type: ignore
                JsonFormatter = JF
            except ImportError:
                pass
        if JsonFormatter is not None:
            handler.setFormatter(
                JsonFormatter(
                    "%(asctime)s %(levelname)s %(name)s %(message)s",
                    rename_fields={"asctime": "ts", "levelname": "level", "name": "logger"},
                )
            )
        else:
            handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))

    root.addHandler(handler)
    root.setLevel(logging.INFO)


def configure_sentry() -> None:
    """Initialise Sentry SDK once at process boot.

    Reads the DSN from the site_settings table first (admin-editable),
    falling back to the SENTRY_DSN env var. A DSN change in admin requires a
    backend restart to take effect — the admin form notes this.
    """
    # Local import — settings table query must not run before SQLAlchemy is
    # configured. `configure_sentry()` is called from main.py at import time
    # which is fine because the engine is created in db.session at that point.
    from app.services.site_settings import get_setting

    dsn = get_setting("integrations.sentry_dsn", env_fallback=settings.SENTRY_DSN)
    if not dsn:
        return
    env = get_setting(
        "integrations.sentry_env",
        env_fallback=settings.SENTRY_ENV or settings.ENVIRONMENT,
    )
    try:
        import sentry_sdk  # type: ignore
        from sentry_sdk.integrations.fastapi import FastApiIntegration  # type: ignore
        from sentry_sdk.integrations.logging import LoggingIntegration  # type: ignore
    except ImportError:
        logging.getLogger("quata.sentry").warning("sentry-sdk not installed; skipping Sentry init.")
        return

    sentry_sdk.init(
        dsn=dsn,
        environment=env,
        traces_sample_rate=0.1,
        send_default_pii=False,
        integrations=[
            FastApiIntegration(),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
    )
    logging.getLogger("quata.sentry").info("Sentry initialised.")
