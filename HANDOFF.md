# Session handoff — pre-launch audit & fixes

**Date:** 2026-07-06 · **Branch:** `main` (all work pushed to `origin/main`).

This file is the pick-up point for continuing the V1 (Cameroon) pre-launch
hardening. It summarises what was audited, what is already fixed & pushed, and
exactly what remains (and why each remaining item is parked).

---

## State of the tree

- Latest commits (both **pushed**, working tree clean):
  - `6b433cb` harden: encrypt TOTP secrets at rest, atomic reset-token, UI perm filters
  - `a836f90` fix(security): close RBAC escalation, resume links, upload & admin bugs
- Verified green on both commits:
  - Backend: `cd backend && .venv/Scripts/python.exe -m pytest -q` → **89 passed**
  - Migration: `alembic upgrade head` chain applies clean up/down (new head `h8m9n0o1p2q3`)
  - Frontend: `cd frontend && npx tsc --noEmit` clean · `npx eslint app components lib` clean · `npm run build` OK

---

## Fixed & pushed (engineering-controllable findings)

**Critical**
- **C1 RBAC escalation** — `staff:manage` can no longer assign a role above its own or edit a more-privileged/super_admin account (`backend/app/api/routes_admin_crud.py`, `_assert_can_assign_role` / `_assert_can_manage_target`).

**High**
- **H1** resume "Open" links normalise to the current host at read time (`routes_admin_extra.py` + `services/uploads.py:normalize_upload_url`); prod guard now rejects localhost `PUBLIC_BASE_URL`/`FRONTEND_URL`.
- **H2** careers resume upload no longer blocked once hCaptcha is enabled (`routes_uploads.py`).
- **H3** upload `folder` sanitised (path traversal) + authed `/uploads` gated behind `content:manage`.
- **H4** applicant `resume_url` validated as an internal upload (blocks phishing/`javascript:` links).
- **H5** partner CSV export un-shadowed (`/partners/{partner_id:int}`) + authenticated blob download.
- **H6** "suspend" now revokes access (`is_active=False`).

**Medium** — draft-content leak closed (`is_published` enforced) · web self check-in can't forge `source="biometric"` · device token constant-time compare · WebSocket honours `pwc` token revocation · applications list bounded + eager-loaded · overview shows an error state (no infinite spinner) · products "Planned" option removed · partners pagination returns a real `total` · messaging individual/department require a recipient/department picker (front + back) · length caps on public inputs.

**Low** — login user-enumeration hardened · device token not echoed on plain edits · robust rate-limit `Retry-After` · notifications bell skips doomed request · markdown editor no longer saves `"null"` in preview mode · `.env.example` documents `/api/v1` · **TOTP secrets encrypted at rest** (Fernet, backward-compatible) · password-reset token claimed atomically · command palette filtered by permission · careers fallback links to `/contact`.

---

## Remaining — needs the BOSS to answer (already sent to him)

1. **Make applicant CVs private?** Today anyone with the file link can download a CV. (Code is ready to lock it behind admin auth once he confirms.)
2. **Force 2FA on all admins?** Only the founder is forced today.
3. **Job perks on the public site real?** ($1,500 learning, 16 weeks parental leave, health for dependents, "hubs in 3 cities", equity) — `frontend/app/(site)/careers/[id]/page.tsx:315`.
4. **Publish the product metrics?** e.g. QUATAPAY "99.95% uptime SLA", "same-day settlement" on pre-launch products — `frontend/lib/ecosystem.ts`.
5. **The 6 "partner" company names are invented placeholders** — `frontend/components/site/logo-cloud.tsx`. Remove or replace?
6. **Confirm day-one public content** (7 products, 7 jobs, 3 blog posts seeded).
7. **Real, monitored contact data?** phone `+237 680044590`, Facebook/Instagram fallback URLs, and which inboxes are watched (info@, support@, careers@, privacy@, security@, …).
8. **OK to show company reg `RC/BDA/2025A/189` + Tax ID publicly?**
9. **Founder name** — "Neba Clovis Ngwa" vs "Clovis Ngwa" (site is inconsistent).
10. **Web clock-in count same as fingerprint?** (attendance policy)
11. **Newsletter** — keep in-DB list or sync to an ESP?
12. **Log/analytics retention** windows (90 / 180 days) OK for Loi n° 2010/012?

Dummy-data list to remove (pending his review): the items in Q3–Q9 above, plus placeholder logos `frontend/public/ecosystem/logos/{88basket,qmediq}.svg`, the fake "live chat" bubble (`chat-bubble.tsx`, just opens email), hardcoded "May 2026" launch dates, and `scripts/fetch_images.py` (stale picsum puller).

---

## Remaining — technical, deferred on purpose (no boss needed)

- **Move admin JWT from `localStorage` → httpOnly cookie + shorten the 7-day session.**
  Deferred because app (`quatadigital.com`) and API (`api.quatadigital.com`) are on **different subdomains** → needs `SameSite=None; Secure` cookies + CSRF tokens + CORS-credentials changes, and can't be fully tested without driving both servers in a browser. **Recommend doing on a dedicated branch with a real browser test.** This is the top remaining hardening item.
- **CSP enforce** — no code change; set env `CSP_ENFORCE=true` after a clean Report-Only window (`frontend/next.config.ts` already toggles it).
- Device webhook: signing is off by default (`DEVICE_REQUIRE_SIGNATURE`) and there's no replay-nonce (5-min window). Fine for single-VPS; revisit with Redis when scaling.

---

## Operational reminders (env, not code)

1. Production backend **must** set `PUBLIC_BASE_URL=https://api.quatadigital.com` and `FRONTEND_URL=https://quatadigital.com` (app refuses to boot otherwise; resume links depend on it).
2. On deploy, run `alembic upgrade head` (new migration `h8m9n0o1p2q3` widens `users.totp_secret`).
3. `cryptography` is now a direct dependency — `pip install -r backend/requirements.txt` before restart.
4. Flip `CSP_ENFORCE=true` when the report window is clean.

---

## To resume on the laptop

```bash
git pull origin main
# backend
cd backend && python -m venv .venv && .venv/Scripts/activate && pip install -r requirements.txt
.venv/Scripts/python.exe -m pytest -q          # expect 89 passed
# frontend
cd ../frontend && npm install && npm run build  # expect success
```

Suggested next task: the httpOnly-cookie auth migration (top of the deferred list), on a branch.
