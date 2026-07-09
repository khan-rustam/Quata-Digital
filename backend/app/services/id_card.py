"""Employee ID card renderer (HRMS 2C).

Renders a print-ready CR80 card (1012×638 px ≈ 3.375"×2.125" at 300 DPI) as PNG
or PDF using Pillow + qrcode — both already project dependencies, so no new
runtime deps and no headless browser needed. The QR encodes the public
verification URL (``FRONTEND_URL/verify/<code>``).
"""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from typing import TYPE_CHECKING

from app.core.config import settings

if TYPE_CHECKING:  # pragma: no cover
    from app.models import User

# CR80 @ ~300 DPI
CARD_W, CARD_H = 1012, 638
BRAND = (14, 91, 74)  # QUATA green
INK = (23, 23, 23)
MUTED = (110, 110, 110)


def _font(size: int, bold: bool = False):
    from PIL import ImageFont

    candidates = (
        [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/Library/Fonts/Arial Bold.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        ]
        if bold
        else [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/Library/Fonts/Arial.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
        ]
    )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    # Pillow >= 10.1 supports a scalable default font.
    return ImageFont.load_default(size=size)


def _initials(name: str) -> str:
    return "".join(p[0] for p in name.split()[:2]).upper() or "?"


def _avatar_disk_path(user: "User"):
    if not user.avatar_url:
        return None
    try:
        from app.services.uploads import resolve_local_upload_path

        return resolve_local_upload_path(user.avatar_url)
    except Exception:  # noqa: BLE001
        return None


def render_id_card_png(user: "User") -> bytes:
    from PIL import Image, ImageDraw
    import qrcode

    card = Image.new("RGB", (CARD_W, CARD_H), "white")
    draw = ImageDraw.Draw(card)

    # Header
    draw.rectangle([0, 0, CARD_W, 108], fill=BRAND)
    draw.text((40, 32), "QUATA DIGITAL ENTERPRISE", font=_font(40, bold=True), fill="white")

    # Photo (circle) — real avatar if we have it on disk, else initials.
    cx, cy, r = 150, 300, 104
    box = (cx - r, cy - r, cx + r, cy + r)
    avatar_path = _avatar_disk_path(user)
    pasted = False
    if avatar_path is not None:
        try:
            photo = Image.open(avatar_path).convert("RGB").resize((2 * r, 2 * r))
            mask = Image.new("L", (2 * r, 2 * r), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, 2 * r, 2 * r), fill=255)
            card.paste(photo, (cx - r, cy - r), mask)
            pasted = True
        except Exception:  # noqa: BLE001
            pasted = False
    if not pasted:
        draw.ellipse(box, fill=(230, 240, 237))
        ini = _initials(user.full_name)
        f = _font(72, bold=True)
        tb = draw.textbbox((0, 0), ini, font=f)
        draw.text((cx - (tb[2] - tb[0]) / 2, cy - (tb[3] - tb[1]) / 2 - tb[1]), ini, font=f, fill=BRAND)

    # Details
    x = 300
    draw.text((x, 172), user.full_name, font=_font(48, bold=True), fill=INK)
    if user.job_title:
        draw.text((x, 236), user.job_title, font=_font(30), fill=MUTED)

    dept = user.department.name if user.department else "—"
    bu = (
        user.department.business_unit.name
        if (user.department and user.department.business_unit)
        else None
    )
    draw.text((x, 300), "EMPLOYEE No.", font=_font(22, bold=True), fill=MUTED)
    draw.text((x, 328), user.employee_number or "—", font=_font(34, bold=True), fill=BRAND)
    draw.text((x, 392), "DEPARTMENT", font=_font(22, bold=True), fill=MUTED)
    draw.text((x, 420), dept + (f"  ·  {bu}" if bu else ""), font=_font(28), fill=INK)

    # QR → public verification URL
    base = (settings.FRONTEND_URL or "").rstrip("/")
    verify_url = f"{base}/verify/{user.verification_code}" if user.verification_code else base
    qr_img = qrcode.make(verify_url).convert("RGB").resize((190, 190))
    card.paste(qr_img, (CARD_W - 230, CARD_H - 250))
    draw.text((CARD_W - 232, CARD_H - 54), "Scan to verify", font=_font(22), fill=MUTED)

    # Footer
    issued = datetime.now(timezone.utc).strftime("%d %b %Y")
    draw.text((40, CARD_H - 54), f"Issued {issued}", font=_font(22), fill=MUTED)

    buf = BytesIO()
    card.save(buf, format="PNG")
    return buf.getvalue()


def render_id_card_pdf(user: "User") -> bytes:
    from PIL import Image

    img = Image.open(BytesIO(render_id_card_png(user))).convert("RGB")
    buf = BytesIO()
    img.save(buf, format="PDF", resolution=300.0)
    return buf.getvalue()
