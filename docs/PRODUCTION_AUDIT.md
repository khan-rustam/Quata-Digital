# QUATA Digital — Production audit (open items only)

The numbered punch-list of everything **still open** before public launch.
Cross-referenced from [`BOSS_ACTIONS.md`](../BOSS_ACTIONS.md) and
[`REMAINING_ITEMS.md`](../REMAINING_ITEMS.md).

Closed items (RBAC, JWT/2FA, lockout, password reset, rate limit, CSP,
security headers, retention, soft-delete trash, settings store, marketing-page
CMS, newsletter broadcast, markdown editor, chrome polish) are not listed
here — see [README.md](../README.md) and [REMAINING_ITEMS.md](../REMAINING_ITEMS.md)
for the shipped surface.

Severity:
- **C** — Critical. Public site cannot go live without it.
- **H** — High. Hardening you don't want to discover the absence of in production.
- **M** — Medium. Polish / content. Site can launch without it but should not stay placeholder.

Status:
- 🚧 **Boss-blocked** — only the boss can resolve (credentials, legal, brand asset, content).
- 🛠 **Engineering** — known scope, scheduled.

Last reviewed: **2026-05-06** · Sprint locked (F-01..F-04, M-02) **fully shipped**.

---

## C — Critical (launch blockers)

### C-02 · Domain canonicalisation on Hostinger

**Status:** 🚧 Boss-blocked.

Walk through [docs/HOSTINGER_DOMAIN_CHECKLIST.md](HOSTINGER_DOMAIN_CHECKLIST.md), reply with the DNS records, pick apex vs `www` as canonical. Engineering wires the redirect at the reverse proxy.

---

## H — High (security / ops hardening)

### H-02 · hCaptcha keys

**Status:** 🚧 Boss-blocked on creating the account.

**How to resolve:**
1. Sign up at https://hcaptcha.com (free).
2. Generate a site key + secret.
3. Sign in to admin → **Site settings → Integrations**.
4. Paste both keys, click Save.

Takes effect within ~15 seconds (the captcha service helper caches reads briefly). Public forms — partner submission, contact, careers, newsletter — all start enforcing immediately.

---

### H-03 · Sentry DSN

**Status:** 🚧 Boss-blocked on creating the project.

**How to resolve:**
1. Sign up at https://sentry.io (free for 5k errors/month).
2. Create a Python project, copy the DSN.
3. Sign in to admin → **Site settings → Integrations** → paste DSN + environment ("production").
4. Restart the backend on the VPS (`bash /home/Quata-Digital/deploy.sh backend` or `sudo systemctl restart quata-digital-backend`). The Sentry SDK only initialises at boot, so a restart is required.

---

## M — Medium (content / polish)

### M-01 · Lawyer review of `/privacy` and `/terms`

**Status:** ✅ Draft pre-seeded → 🚧 boss verifies with lawyer.

The current legal text is auto-loaded as section content the moment the boss opens admin. Open `/admin/cms/pages/privacy`, click **Publish** to make it live, then send the URL to a Cameroonian lawyer for Loi n° 2010/012 review. They edit through admin; no engineering involvement needed.

Same flow for `/terms`.

Confirm `privacy@quatadigital.com` is monitored.

---

### M-03 · Founder photo

**Status:** 🚧 Boss-blocked.

Edit the **About** page in admin → click into any section that supports an image (e.g. add a hero with a portrait, or an `image_text` section) → upload the headshot directly. No file naming convention required.

---

### M-04 · Product screenshots (QUATAPAY, ABAQWA)

**Status:** 🚧 Boss-blocked.

Two paths:
1. **Quick:** edit the existing product entry at `/admin/products` → upload a hero image. Works today.
2. **Section-based:** open `/admin/cms/pages/ecosystem/quatapay` (currently empty), add a Hero section with the screenshot, publish. (Requires AA below — section pre-seeding for product pages.)

---

### M-05 · Real 88BASKET + QMEDIQ logos

**Status:** 🚧 Boss-blocked.

Replace the placeholder SVGs at `frontend/public/ecosystem/logos/88basket.svg` and `qmediq.svg` (drop-in, same filename, no code change). Or upload via `/admin/products` once a `logo_url` field is exposed (small follow-up).

---

### M-06 · Partner / press logos

**Status:** 🚧 Boss-blocked.

Empty until permission per logo. When ready, edit Home page in admin → add a `logo_cloud` section → upload approved logos.

---

### M-07 · Lock the launch date

**Status:** 🚧 Boss-blocked.

Currently appears as "May 2026" in the seeded Hero / About / Timeline sections. Once the date firms up, edit each affected section in admin and Save. No code change needed.

---

### M-08 · Public phone, email, address, social

**Status:** 🚧 Boss-blocked.

**Admin → Site settings → Contact info** for phone / email / address / support hours. **Site settings → Social** for LinkedIn / Twitter / Instagram / YouTube / Facebook URLs. Footer + contact page pick up changes within ~10 seconds.

---

### M-09 · TBA launch dates per product

**Status:** 🚧 Boss-blocked.

`/admin/products` → edit each of 88BASKET, O3MALL, QMEDIQ → set status + tagline mentioning the date.

---

### M-10 · Per-product `websiteUrl`

**Status:** 🛠 Engineering follow-up.

Field exists in the legacy `Product` model but no admin UI yet. Small follow-up task once any product has a public URL.

---

## AA / AB / AC — Engineering follow-ups

### AA · Per-product CMS pages

**Status:** 🛠 Engineering, post-launch.

The 7 product pages (`/ecosystem/quatapay`, etc) currently render from the legacy `Product` model. The CMS schema already supports them as `page_type=product` with a strict allowed-section list — they just need section pre-seeding from the existing static React copy and the public `[slug]/page.tsx` checks the CMS first (already wired).

Effort: ~1 day to write 7 starter section sets + verify rendering.

---

### AB · Per-partner-type CMS pages

**Status:** 🛠 Engineering, post-launch.

Same shape as AA for the 4 partner-type pages (`/partners/business`, `strategic`, `investor`, `service`). CMS plumbing is in place; just needs starter content.

---

### AC · TipTap block editor for blog

**Status:** 🛠 Engineering, post-launch.

Markdown editor with toolbar (current) covers ~90% of editorial needs. TipTap as Option B once we observe how the boss uses the markdown editor in practice.

---

## What's actually blocking launch

After this sprint, the **only remaining items that gate going public** are:

1. **C-02** (domain canonicalisation — Hostinger) — needs a 30-minute DNS check + redirect decision.
2. **H-02** (hCaptcha) — boss creates account, pastes keys.
3. **M-08** (public phone/email/social) — boss types into admin.

Items 4–8 in [REMAINING_ITEMS.md](../REMAINING_ITEMS.md) (lawyer review, brand assets, launch date, product launch dates) can land in the days after launch — none of them break the site.

---

## Resolved this sprint

The previous version of this audit listed C-01 (Postgres URL), C-03 (Cloudflare), H-01 (SMTP), H-04 (backup) as critical/high. All four were either resolved (Postgres provisioned, SMTP wired) or descoped (Cloudflare and first backup are post-launch).

The original audit's **all 13 H-tier engineering items** (auth baseline, RBAC, rate limit, CSP, headers, upload validation, biometric webhook security, prod-safety guard, observability, retention, etc.) were already shipped before this sprint started. F-01 to F-04 + M-02 closed everything else that engineering could close from inside the codebase.
