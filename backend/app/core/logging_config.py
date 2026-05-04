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
    if not settings.SENTRY_DSN:
        return
    try:
        import sentry_sdk  # type: ignore
        from sentry_sdk.integrations.fastapi import FastApiIntegration  # type: ignore
        from sentry_sdk.integrations.logging import LoggingIntegration  # type: ignore
    except ImportError:
        logging.getLogger("quata.sentry").warning("sentry-sdk not installed; skipping Sentry init.")
        return

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.SENTRY_ENV or settings.ENVIRONMENT,
        traces_sample_rate=0.1,
        send_default_pii=False,
        integrations=[
            FastApiIntegration(),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
    )
    logging.getLogger("quata.sentry").info("Sentry initialised.")
