#!/usr/bin/env python
"""QUATA backend dev runner.

One command to boot the API with sane defaults. Run from the `backend/`
directory (or anywhere — it cd's to its own location):

    python start.py                  # 127.0.0.1:8000 with --reload
    python start.py --host 0.0.0.0   # bind all interfaces (LAN/Docker)
    python start.py --port 8080      # custom port
    python start.py --no-reload      # production-style boot, no watcher
    python start.py --migrate        # run `alembic upgrade head` first
    python start.py --reset-db       # delete the dev SQLite file before booting

Run `python start.py --help` for the full flag list.
"""
from __future__ import annotations

import argparse
import os
import socket
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
os.chdir(HERE)
# Make `from app.main import app` work no matter where you invoked us from.
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


# ---------------- helpers ----------------

DIM = "\x1b[2m"
GREEN = "\x1b[32m"
YELLOW = "\x1b[33m"
RED = "\x1b[31m"
BOLD = "\x1b[1m"
RESET = "\x1b[0m"


def info(label: str, value: str) -> None:
    print(f"  {DIM}{label:<14}{RESET} {value}")


def banner() -> None:
    print(f"{BOLD}{GREEN}QUATA backend{RESET} {DIM}dev runner{RESET}")


def port_is_taken(host: str, port: int) -> int | None:
    """Return the PID owning `port`, or None if the port is free.

    Tries to bind first (cheap), then falls back to the OS-specific
    process listing only if binding fails.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((host, port))
        return None
    except OSError:
        # Something owns it. Try to identify the PID — best-effort.
        if sys.platform == "win32":
            try:
                import subprocess

                out = subprocess.check_output(
                    ["netstat", "-ano", "-p", "TCP"], text=True, errors="ignore"
                )
                for line in out.splitlines():
                    parts = line.split()
                    if (
                        len(parts) >= 5
                        and "LISTENING" in line
                        and parts[1].endswith(f":{port}")
                    ):
                        return int(parts[-1])
            except Exception:  # noqa: BLE001
                return -1
        else:
            try:
                import subprocess

                out = subprocess.check_output(
                    ["lsof", "-iTCP", f"-sTCP:LISTEN", "-Pn", "-ti", f":{port}"],
                    text=True,
                )
                pids = [int(x) for x in out.split() if x.strip().isdigit()]
                return pids[0] if pids else -1
            except Exception:  # noqa: BLE001
                return -1
        return -1
    finally:
        sock.close()


def kill_pid(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        if sys.platform == "win32":
            import subprocess

            subprocess.check_call(
                ["taskkill", "/F", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            os.kill(pid, 9)
        return True
    except Exception:  # noqa: BLE001
        return False


def reset_dev_db(db_url: str) -> None:
    """Delete the SQLite file when DATABASE_URL points at one."""
    if not db_url.startswith("sqlite"):
        print(f"{YELLOW}--reset-db only supports SQLite. DATABASE_URL is {db_url}.{RESET}")
        return
    # sqlite:///./quata.db  →  ./quata.db
    path = db_url.replace("sqlite:///", "", 1)
    target = Path(path).resolve()
    if target.exists():
        target.unlink()
        print(f"{YELLOW}reset:{RESET} deleted {target}")
    else:
        print(f"{DIM}reset: {target} did not exist{RESET}")


def run_alembic_upgrade() -> None:
    import subprocess

    print(f"{DIM}migrate: alembic upgrade head{RESET}")
    rc = subprocess.call([sys.executable, "-m", "alembic", "upgrade", "head"])
    if rc != 0:
        print(f"{RED}alembic upgrade failed (exit {rc}). Aborting boot.{RESET}")
        sys.exit(rc)


# ---------------- main ----------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    parser.add_argument("--no-reload", dest="reload", action="store_false", default=True)
    parser.add_argument("--workers", type=int, default=1, help="Only used when --no-reload is set")
    parser.add_argument("--migrate", action="store_true", help="Run alembic upgrade head before booting")
    parser.add_argument("--reset-db", action="store_true", help="Delete the dev SQLite file before booting")
    parser.add_argument(
        "--kill-port",
        action="store_true",
        help="If --port is taken, kill the owning PID and continue",
    )
    parser.add_argument("--log-level", default=os.environ.get("LOG_LEVEL", "info"))
    args = parser.parse_args()

    # Sensible dev defaults — but never overwrite anything the user set.
    os.environ.setdefault("ENVIRONMENT", "development")
    os.environ.setdefault("EMAIL_BACKEND", "console")

    # Lazy import after env is set so the production guards don't fire on
    # an unset ENVIRONMENT.
    from app.core.config import settings  # noqa: WPS433

    banner()
    info("environment", settings.ENVIRONMENT)
    info("database", settings.DATABASE_URL)
    info("email", settings.EMAIL_BACKEND)
    info("upload dir", settings.UPLOAD_DIR)
    info("bind", f"http://{args.host}:{args.port}")
    info("docs", f"http://{args.host}:{args.port}/docs")
    info("api", f"http://{args.host}:{args.port}{settings.API_PREFIX}")
    print()

    # Optional pre-boot steps.
    if args.reset_db:
        reset_dev_db(settings.DATABASE_URL)
    if args.migrate:
        run_alembic_upgrade()

    # Port check.
    pid = port_is_taken(args.host, args.port)
    if pid is not None:
        if args.kill_port:
            owner = f"PID {pid}" if pid > 0 else "an unknown process"
            print(f"{YELLOW}port {args.port} held by {owner} — killing…{RESET}")
            if pid > 0:
                kill_pid(pid)
        else:
            owner = f"PID {pid}" if pid > 0 else "an unknown process"
            print(
                f"{RED}port {args.port} is in use ({owner}). "
                f"Re-run with --kill-port or --port <other>.{RESET}"
            )
            sys.exit(2)

    # Hand off to uvicorn.
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=None if args.reload else args.workers,
        log_level=args.log_level,
        # Reload only the source we care about; node_modules and uploads
        # don't need to trigger restarts.
        reload_dirs=[str(HERE / "app")] if args.reload else None,
    )


if __name__ == "__main__":
    main()
