"""Payslip PDF generation from a SalaryRecord, drawn with Pillow (same
toolchain as the ID-card service) so no extra dependency is needed."""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from typing import TYPE_CHECKING

from app.services.id_card import BRAND, INK, MUTED, _font

if TYPE_CHECKING:  # pragma: no cover
    from app.models import SalaryRecord, User

# A4 portrait @ ~150 DPI.
PAGE_W, PAGE_H = 1240, 1754
MARGIN = 90
LINE = (225, 225, 225)
SOFT = (247, 247, 244)


def _money(amount: int, currency: str) -> str:
    return f"{amount:,} {currency}"


def _period(record: "SalaryRecord") -> str:
    d = record.effective_date
    return d.strftime("%B %Y") if d else "—"


def render_payslip_pdf(user: "User", record: "SalaryRecord") -> bytes:
    img = _build_payslip(user, record)
    buf = BytesIO()
    img.save(buf, format="PDF", resolution=150.0)
    return buf.getvalue()


def _build_payslip(user: "User", record: "SalaryRecord"):
    from PIL import Image, ImageDraw

    gross = record.basic_salary + record.allowances + record.bonus + record.overtime
    deductions = (
        record.tax + record.pension + record.insurance
        + record.loan_deduction + record.advance_deduction
    )
    net = gross - deductions
    cur = record.currency or "XAF"

    img = Image.new("RGB", (PAGE_W, PAGE_H), "white")
    draw = ImageDraw.Draw(img)
    right = PAGE_W - MARGIN

    def row(y: int, label: str, amount: int, *, bold: bool = False, muted: bool = False) -> int:
        f = _font(30, bold=bold)
        draw.text((MARGIN + 20, y), label, font=f, fill=(INK if not muted else MUTED))
        val = _money(amount, cur)
        w = draw.textlength(val, font=f)
        draw.text((right - 20 - w, y), val, font=f, fill=INK)
        return y + 52

    def section(y: int, title: str) -> int:
        draw.text((MARGIN, y), title, font=_font(24, bold=True), fill=BRAND)
        return y + 44

    # Header band.
    draw.rectangle([0, 0, PAGE_W, 150], fill=BRAND)
    draw.text((MARGIN, 40), "QUATA DIGITAL ENTERPRISE", font=_font(44, bold=True), fill="white")
    draw.text((MARGIN, 96), "Payslip", font=_font(30), fill=(220, 235, 230))

    # Employee + period block.
    y = 210
    draw.text((MARGIN, y), user.full_name, font=_font(40, bold=True), fill=INK)
    y += 56
    sub = user.job_title or "—"
    if user.department:
        sub += f"  ·  {user.department.name}"
    draw.text((MARGIN, y), sub, font=_font(28), fill=MUTED)
    y += 46
    draw.text((MARGIN, y), f"Employee No. {user.employee_number or '—'}", font=_font(26), fill=MUTED)
    # Pay period (right-aligned).
    period = f"Pay period: {_period(record)}"
    pw = draw.textlength(period, font=_font(28, bold=True))
    draw.text((right - pw, 266), period, font=_font(28, bold=True), fill=INK)
    y += 70

    # Earnings.
    y = section(y, "EARNINGS")
    draw.rectangle([MARGIN, y, right, y], fill=LINE)
    y += 16
    y = row(y, "Basic salary", record.basic_salary)
    y = row(y, "Allowances", record.allowances)
    y = row(y, "Bonus", record.bonus)
    y = row(y, "Overtime", record.overtime)
    draw.rectangle([MARGIN + 20, y, right - 20, y + 2], fill=LINE)
    y += 14
    y = row(y, "Gross earnings", gross, bold=True)
    y += 30

    # Deductions.
    y = section(y, "DEDUCTIONS")
    draw.rectangle([MARGIN, y, right, y], fill=LINE)
    y += 16
    y = row(y, "Tax", record.tax)
    y = row(y, "Pension", record.pension)
    y = row(y, "Insurance", record.insurance)
    y = row(y, "Loan repayment", record.loan_deduction)
    y = row(y, "Advance recovery", record.advance_deduction)
    draw.rectangle([MARGIN + 20, y, right - 20, y + 2], fill=LINE)
    y += 14
    y = row(y, "Total deductions", deductions, bold=True)
    y += 40

    # Net pay band.
    draw.rectangle([MARGIN, y, right, y + 92], fill=BRAND)
    draw.text((MARGIN + 24, y + 26), "NET PAY", font=_font(34, bold=True), fill="white")
    net_s = _money(net, cur)
    nw = draw.textlength(net_s, font=_font(38, bold=True))
    draw.text((right - 24 - nw, y + 22), net_s, font=_font(38, bold=True), fill="white")
    y += 140

    # Meta.
    if record.payment_method:
        draw.text((MARGIN, y), f"Payment method: {record.payment_method}", font=_font(26), fill=MUTED)
        y += 44
    if record.notes:
        draw.text((MARGIN, y), f"Note: {record.notes[:120]}", font=_font(24), fill=MUTED)
        y += 44

    # Footer.
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    draw.text(
        (MARGIN, PAGE_H - MARGIN),
        f"Generated {stamp} · System-generated payslip, no signature required.",
        font=_font(22),
        fill=MUTED,
    )

    return img
