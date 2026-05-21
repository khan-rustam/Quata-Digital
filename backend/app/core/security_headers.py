"""Security response-header middleware.

Adds the modern hardening headers (CSP, HSTS, X-Frame-Options, X-Content-
Type-Options, Referrer-Policy, Permissions-Policy, COOP/CORP) to every
response.

Toggles:
- ``CSP_ENFORCE`` flips Content-Security-Policy between Report-Only and
  enforce. Start in Report-Only for ~30 days in production, watch the
  Sentry/CSP report stream, then enforce.
- ``HSTS_PRELOAD`` adds ``; preload`` once you've submitted the domain to
  https://hstspreload.org and want browsers to refuse plain HTTP forever.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


def _build_csp() -> str:
    """Conservative CSP appropriate for the public marketing site + API.

    - The API serves JSON, OG images, and static uploads. None of that
      executes script in the browser, so the CSP only matters when an
      authenticated admin fetches a JSON error page directly in the URL
      bar; still worth defending in depth.
    - hCaptcha (used on public forms) and Sentry (used on the frontend)
      need explicit allow-lists; both are also referenced by the frontend
      Next.js CSP, but keeping them here means a direct API hit is safe.
    """

    directives = [
        "default-src 'none'",
        # The API itself never serves HTML that needs script/style.
        "script-src 'none'",
        "style-src 'none'",
        "img-src 'self' data:",
        # Allow loading uploaded media + same-origin font fallback for the
        # FastAPI Swagger fallback (kept disabled in prod by main.py).
        "font-src 'self' data:",
        "connect-src 'self'",
        "frame-ancestors 'none'",
        "base-uri 'none'",
        "form-action 'self'",
        "object-src 'none'",
    ]
    return "; ".join(directives)


_CSP_VALUE = _build_csp()


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Inject defence-in-depth response headers on every response."""

    def __init__(
        self,
        app,
        *,
        csp_enforce: bool = False,
        hsts_preload: bool = False,
        is_production: bool = False,
    ) -> None:
        super().__init__(app)
        self._csp_enforce = csp_enforce
        self._hsts_preload = hsts_preload
        self._is_production = is_production

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        response: Response = await call_next(request)
        headers = response.headers

        csp_header = (
            "Content-Security-Policy"
            if self._csp_enforce
            else "Content-Security-Policy-Report-Only"
        )
        headers.setdefault(csp_header, _CSP_VALUE)
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        headers.setdefault(
            "Permissions-Policy",
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()",
        )
        headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        headers.setdefault("Cross-Origin-Resource-Policy", "same-site")

        if self._is_production:
            hsts = "max-age=31536000; includeSubDomains"
            if self._hsts_preload:
                hsts += "; preload"
            headers.setdefault("Strict-Transport-Security", hsts)

        return response
