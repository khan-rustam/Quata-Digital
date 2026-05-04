"""hCaptcha verification helper.

Activates only when both `HCAPTCHA_SITE_KEY` and `HCAPTCHA_SECRET_KEY` are
set. With no keys, `verify_captcha_or_raise` is a no-op so dev and unconfigured
environments continue to work.
"""
from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from typing import Optional

from fastapi import HTTPException, status

from app.core.config import settings

log = logging.getLogger(__name__)

HCAPTCHA_VERIFY_URL = "https://api.hcaptcha.com/siteverify"


def captcha_enabled() -> bool:
    return bool(settings.HCAPTCHA_SITE_KEY and settings.HCAPTCHA_SECRET_KEY)


def verify_captcha_or_raise(token: Optional[str], remote_ip: Optional[str] = None) -> None:
    """Validate an hCaptcha token. Raises 400 on failure.

    No-op when keys aren't configured, so unprotected dev still works.
    """
    if not captcha_enabled():
        return
    if not token:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Captcha token missing. Refresh the page and try again.",
        )
    payload = {"secret": settings.HCAPTCHA_SECRET_KEY, "response": token}
    if remote_ip:
        payload["remoteip"] = remote_ip
    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(HCAPTCHA_VERIFY_URL, data=data)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        log.warning("hCaptcha verify failed network: %s", exc)
        # Fail closed: when captcha is on, an unreachable provider should
        # not let the request through.
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "Captcha verification temporarily unavailable. Please try again.",
        ) from exc
    if not body.get("success"):
        log.info("hCaptcha rejected: %s", body.get("error-codes"))
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Captcha verification failed.",
        )
