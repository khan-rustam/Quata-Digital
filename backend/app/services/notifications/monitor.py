"""Infrastructure + payment-gateway monitoring.

Samples the host and the app's own dependencies, then publishes
``❌ SYSTEM ALERT`` events when something is wrong and a recovery event when
it comes back. Deliberately stdlib-only (``shutil``, ``os``, ``/proc``) so
monitoring adds no dependency and can't itself become the thing that breaks.

Two anti-noise mechanisms:

* **Edge triggering.** An alert fires when a check *changes* from healthy to
  unhealthy, not on every sample. Recovery fires on the way back.
* **Hourly dedupe keys.** Process restarts reset the in-memory edge state,
  so the dedupe key also pins each condition to one alert per hour. Belt
  and braces — a crash-looping box must not machine-gun the administrators.
"""
from __future__ import annotations

import logging
import os
import shutil
import threading
from datetime import datetime, timezone
from typing import Optional

from app.core.config import settings as env_settings

from . import settings_store
from .catalog import DEFAULT_PLATFORM
from .dispatch import emit


log = logging.getLogger("quata.notifications.monitor")

# check name → currently-unhealthy? Guarded because the worker and the web
# process can both run checks.
_STATE: dict[str, bool] = {}
_STATE_LOCK = threading.Lock()


def _hour_bucket() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H")


def _transition(check: str, unhealthy: bool) -> Optional[str]:
    """Record the new state and return "down", "up", or None if unchanged."""
    with _STATE_LOCK:
        previous = _STATE.get(check)
        _STATE[check] = unhealthy
    if previous is None:
        # First observation: only report if it's already bad. A healthy
        # first sample is the normal case and isn't news.
        return "down" if unhealthy else None
    if previous == unhealthy:
        return None
    return "down" if unhealthy else "up"


def _alert(event_key: str, check: str, payload: dict, *, priority: Optional[str] = None) -> None:
    emit(
        event_key,
        platform=DEFAULT_PLATFORM,
        payload=payload,
        reference=check.upper().replace("_", "-"),
        priority=priority,
        dedupe_key=f"monitor:{check}:{event_key}:{_hour_bucket()}",
    )


# ---------------------------------------------------------------------------
# Samplers
# ---------------------------------------------------------------------------

def disk_usage_percent(path: Optional[str] = None) -> Optional[float]:
    try:
        usage = shutil.disk_usage(path or env_settings.UPLOAD_DIR or ".")
    except OSError:
        return None
    if not usage.total:
        return None
    return round((usage.used / usage.total) * 100, 1)


def memory_usage_percent() -> Optional[float]:
    """Linux only — reads /proc/meminfo. Returns None elsewhere."""
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as handle:
            values: dict[str, float] = {}
            for line in handle:
                key, _, rest = line.partition(":")
                parts = rest.split()
                if parts:
                    values[key.strip()] = float(parts[0])
    except (OSError, ValueError):
        return None
    total = values.get("MemTotal")
    available = values.get("MemAvailable")
    if not total or available is None:
        return None
    return round(((total - available) / total) * 100, 1)


def cpu_load_percent() -> Optional[float]:
    """1-minute load average as a percentage of available cores."""
    try:
        load1 = os.getloadavg()[0]
    except (OSError, AttributeError):
        return None
    cores = os.cpu_count() or 1
    return round((load1 / cores) * 100, 1)


def database_ok() -> bool:
    from sqlalchemy import text

    from app.db.session import SessionLocal

    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("monitor.database_check_failed", extra={"error": str(exc)[:200]})
        return False


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def _check_resource(
    *,
    check: str,
    value: Optional[float],
    threshold: float,
    alert_key: str,
    label: str,
) -> Optional[dict]:
    if value is None:
        return None  # unsupported platform — not a failure
    edge = _transition(check, value >= threshold)
    if edge == "down":
        _alert(
            alert_key,
            check,
            {
                "host": os.uname().nodename if hasattr(os, "uname") else "unknown",
                "metric": label,
                "value": f"{value}%",
                "threshold": f"{threshold}%",
            },
        )
    elif edge == "up":
        _alert(
            "infra.server_recovered",
            f"{check}_recovered",
            {
                "host": os.uname().nodename if hasattr(os, "uname") else "unknown",
                "metric": label,
                "value": f"{value}%",
                "threshold": f"{threshold}%",
            },
        )
    return {"check": check, "value": value, "threshold": threshold, "healthy": value < threshold}


def run_checks() -> dict:
    """One monitoring sweep. Called by the notification worker."""
    results: list[dict] = []

    cpu = _check_resource(
        check="cpu",
        value=cpu_load_percent(),
        threshold=settings_store.cpu_threshold(),
        alert_key="infra.high_cpu",
        label="CPU load",
    )
    if cpu:
        results.append(cpu)

    memory = _check_resource(
        check="memory",
        value=memory_usage_percent(),
        threshold=settings_store.memory_threshold(),
        alert_key="infra.high_ram",
        label="Memory usage",
    )
    if memory:
        results.append(memory)

    disk_value = disk_usage_percent()
    disk = _check_resource(
        check="disk",
        value=disk_value,
        threshold=settings_store.disk_threshold(),
        alert_key="infra.high_disk",
        label="Disk usage",
    )
    if disk:
        results.append(disk)

    # A nearly-full disk is a distinct, more urgent condition than "high".
    if disk_value is not None:
        edge = _transition("storage_low", disk_value >= 95.0)
        if edge == "down":
            _alert(
                "infra.storage_low",
                "storage_low",
                {"metric": "Free storage", "value": f"{round(100 - disk_value, 1)}% free"},
            )

    db_healthy = database_ok()
    edge = _transition("database", not db_healthy)
    if edge == "down":
        _alert("infra.database_disconnected", "database", {"service": "PostgreSQL / primary database"})
    elif edge == "up":
        _alert("infra.server_recovered", "database_recovered", {"service": "Primary database"})
    results.append({"check": "database", "healthy": db_healthy})

    queue_result = check_queue()
    if queue_result:
        results.append(queue_result)

    api_result = check_api_reachable()
    if api_result:
        results.append(api_result)

    return {"checked_at": datetime.now(timezone.utc).isoformat(), "results": results}


def check_queue() -> Optional[dict]:
    """Alert when the background job queue accumulates failures."""
    try:
        from app.services.queue import queue_status

        status = queue_status()
    except Exception as exc:  # noqa: BLE001
        _alert("infra.queue_failure", "queue", {"error": str(exc)[:200]})
        return {"check": "queue", "healthy": False}

    if status.get("mode") != "redis":
        return None  # synchronous mode has no queue to fail
    if status.get("error"):
        edge = _transition("queue", True)
        if edge == "down":
            _alert("infra.queue_failure", "queue", {"service": "RQ", "error": str(status["error"])[:200]})
        return {"check": "queue", "healthy": False}

    failed = int(status.get("failed") or 0)
    unhealthy = failed > 0
    edge = _transition("queue", unhealthy)
    if edge == "down":
        _alert(
            "infra.job_failure",
            "queue",
            {"service": "RQ", "metric": "Failed jobs", "value": failed, "queue": status.get("queue")},
        )
    elif edge == "up":
        _alert("infra.server_recovered", "queue_recovered", {"service": "RQ background queue"})
    return {"check": "queue", "healthy": not unhealthy, "failed_jobs": failed}


# ---------------------------------------------------------------------------
# Event helpers other parts of the app call directly
# ---------------------------------------------------------------------------

def _host() -> str:
    return os.uname().nodename if hasattr(os, "uname") else "unknown"


def report_startup() -> None:
    """Announce that the API came up — covers 'server restarted'."""
    _alert(
        "infra.server_restarted",
        "boot",
        {
            "host": _host(),
            "service": env_settings.PROJECT_NAME,
            "environment": env_settings.ENVIRONMENT,
        },
    )


def report_shutdown() -> None:
    """Announce that the API is going down — covers 'server offline'.

    Delivered synchronously: the process is about to exit, so handing this
    to a background worker would lose it. A clean stop (deploy, restart) is
    reported here; an *unclean* stop is caught by the watchdog below, which
    runs in the separate worker process.
    """
    event_id = emit(
        "infra.server_offline",
        platform=DEFAULT_PLATFORM,
        payload={
            "host": _host(),
            "service": env_settings.PROJECT_NAME,
            "environment": env_settings.ENVIRONMENT,
            "detail": "The API process is shutting down.",
        },
        reference="SERVER-OFFLINE",
        dedupe_key=f"monitor:shutdown:{_hour_bucket()}",
        dispatch=False,
    )
    if not event_id:
        return
    from .dispatch import deliver_event

    try:
        deliver_event(event_id)
    except Exception:  # noqa: BLE001 — never block or fail a shutdown
        pass


def check_api_reachable() -> Optional[dict]:
    """Probe the API's readiness endpoint from the worker process.

    This is what catches the case ``report_shutdown`` cannot: a crash, an
    OOM kill, or a hung uvicorn. The worker is a separate process, so it
    survives to notice — and to report the recovery afterwards.

    Returns None unless ``NOTIFY_HEALTHCHECK_URL`` names a URL to probe. It
    is opt-in on purpose: a watchdog pointed at the wrong host reports
    outages that aren't happening, which is worse than no watchdog at all.
    """
    import urllib.error
    import urllib.request

    url = (env_settings.NOTIFY_HEALTHCHECK_URL or "").strip()
    if not url:
        return None

    healthy = False
    detail = ""
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            healthy = response.status == 200
            if not healthy:
                detail = f"HTTP {response.status}"
    except urllib.error.HTTPError as exc:
        detail = f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001 — URLError, timeout, DNS
        detail = f"{type(exc).__name__}: {exc}"

    edge = _transition("api", not healthy)
    if edge == "down":
        _alert(
            "infra.api_unavailable",
            "api",
            {"service": env_settings.PROJECT_NAME, "endpoint": url, "error": detail[:300]},
        )
    elif edge == "up":
        _alert(
            "infra.server_recovered",
            "api_recovered",
            {"service": env_settings.PROJECT_NAME, "endpoint": url},
        )
    return {"check": "api", "healthy": healthy, "detail": detail}


def report_application_error(
    *, path: str, method: str, error: str, request_id: Optional[str] = None
) -> None:
    """Unhandled exception escaped a request handler."""
    emit(
        "infra.application_error",
        platform=DEFAULT_PLATFORM,
        payload={
            "service": env_settings.PROJECT_NAME,
            "endpoint": f"{method} {path}",
            "error": error[:400],
        },
        reference=request_id or path[:160],
        # One alert per endpoint per hour: a broken route hit 5,000 times
        # is one problem, not 5,000 messages.
        dedupe_key=f"apperror:{method}:{path}:{_hour_bucket()}",
    )


def report_job_failure(*, job: str, error: str) -> None:
    """A background job blew up."""
    emit(
        "infra.job_failure",
        platform=DEFAULT_PLATFORM,
        payload={"service": job, "error": error[:400]},
        reference=job[:160],
        dedupe_key=f"jobfail:{job}:{_hour_bucket()}",
    )


def report_backup(*, ok: bool, detail: str = "", size: Optional[str] = None) -> None:
    """Database backup outcome — call from the backup script."""
    emit(
        "infra.database_backup_completed" if ok else "infra.database_backup_failed",
        platform=DEFAULT_PLATFORM,
        payload={"service": "Database backup", "detail": detail[:400], "size": size},
        reference="DB-BACKUP",
    )


def report_gateway(event_key: str, *, gateway: str = "MTN MoMo", **payload) -> None:
    """Payment-gateway monitoring hook.

    ``report_gateway("gateway.momo_unavailable", error="504 from collection API")``
    """
    emit(
        event_key,
        platform=DEFAULT_PLATFORM,
        payload={"service": gateway, **payload},
        reference=gateway.upper().replace(" ", "-"),
        dedupe_key=f"gateway:{event_key}:{_hour_bucket()}",
    )
