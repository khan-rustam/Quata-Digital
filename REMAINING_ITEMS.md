# QUATA Digital — Remaining items (final, deferred only)

Last reviewed: **2026-05-04**.
Build is **green** (`npm run lint` 0/0, `npm run build` 55/55 prerendered).

Engineering has closed every dev-doable item. Everything below is a
hard external dependency — boss-owned credentials, legal sign-off,
brand assets, or a hosting decision. **None of these can be resolved
from inside the codebase.**

---

## ✅ What was just closed in this pass

For audit-ability:

- React 19 strict-effect compliance — converted `cookie-banner`,
  `page-view-tracker` and `notifications-dropdown` from
  `setState`-in-effect patterns to `useSyncExternalStore` (the
  React-idiomatic pattern). Three eslint-disables removed.
- Domain unification — every legacy `quata.digital` reference replaced
  with `quatadigital.com` across `robots.ts`, `opengraph-image.tsx`,
  admin login + forgot-password placeholders, partners contact link,
  CMS markdown placeholder. Sitemap fallback also unified.
- Phone-number stub removed — footer + contact page now read
  `NEXT_PUBLIC_CONTACT_PHONE`. The row is hidden until the env var is
  set (no more "+237 — live at launch" copy in production).
- CSP shipped in **Report-Only** mode in `next.config.ts`. Browsers
  report violations to devtools without breaking the page; flip the
  header name to enforce after a clean reporting window.
- 88basket and qmediq placeholder logos repolished (still placeholders,
  but cleaner geometry + bigger canvas at 512×512).
- Production-deploy section added to [`README.md`](README.md) with
  required env-var matrix, first-time-deploy commands, and pre-launch
  checklist.
- Operational runbook authored at
  [`docs/RUNBOOK.md`](docs/RUNBOOK.md) — deploy, rollback, common
  incidents, backup/restore, secret rotation, escalation.
- Admin user manual authored at
  [`docs/ADMIN_USER_MANUAL.md`](docs/ADMIN_USER_MANUAL.md) — sign-in,
  partner triage, content publishing, staff management, security
  checklist.

---

## 🚨 BOSS-ONLY (blocks public launch)

These are hard-blocked on the boss / external accounts. Same as
[`BOSS_ACTIONS.md`](BOSS_ACTIONS.md) — kept here as a single dashboard.

| # | Item | What's needed | Where it goes |
|---|---|---|---|
| 1 | **Production Postgres** | Managed Postgres URL (Neon / Supabase / Railway / RDS) | `DATABASE_URL` in backend `.env` |
| 2 | **Domain decision** | Apex (`quatadigital.com`) or `www.` canonical, plus DNS | DNS + `NEXT_PUBLIC_SITE_URL` |
| 3 | **SMTP2GO credentials** | Username / password / verified sender domain (SPF, DKIM, DMARC) | `SMTP_*` + `EMAIL_BACKEND=smtp` in backend `.env` |
| 4 | **Sentry DSN** (or explicit "skip") | Sentry account + DSN | `SENTRY_DSN` + `SENTRY_ENV` in backend `.env` |
| 5 | **hCaptcha keys** | Site key + secret from hcaptcha.com | `HCAPTCHA_*` (backend) + `NEXT_PUBLIC_HCAPTCHA_SITE_KEY` (frontend) |
| 6 | **Cloudflare account** | Account with apex domain proxied | DNS + page rules |
| 7 | **Backup plan + retention** | Frequency / retention / location decision | Engineering writes script after decision |
| 8 | **Legal sign-off** | Cameroonian lawyer review of `/privacy` and `/terms`; confirm `privacy@quatadigital.com` is monitored | Drop-in red-line edits to those page files |
| 9 | **Newsletter ESP** | Either "keep in-DB" or pick (Mailchimp / ConvertKit / Buttondown) + API key | Wire-up after decision |

---

## 🎨 BOSS-ONLY (assets — site is functional without them, but polish needed)

| # | Item | Where it lives | Drop-in path |
|---|---|---|---|
| A | **Real 88BASKET logo** | placeholder SVG at `frontend/public/ecosystem/logos/88basket.svg` | Replace with `88basket.png` (or `.svg`); no code change needed |
| B | **Real QMEDIQ logo** | placeholder SVG at `frontend/public/ecosystem/logos/qmediq.svg` | Replace with `qmediq.png` (or `.svg`); no code change needed |
| C | **Founder photo** | stock placeholder at `frontend/public/images/about/founder.jpg` | Same filename, real headshot |
| D | **QUATAPAY dashboard screenshot** | stock placeholder at `frontend/public/images/ecosystem/quatapay/hero.jpg` | Same filename, real dashboard |
| E | **ABAQWA dashboard screenshot** | stock placeholder at `frontend/public/images/ecosystem/abaqwa/hero.jpg` | Same filename, real dashboard |
| F | **Partner / press logos** | none yet — site has no logo wall | Boss approves which partners can be displayed; engineering adds the wall |
| G | **First-party photography** (optional) | stock images across `partners/*/*.jpg`, `careers/hero.jpg`, `about/hero.jpg`, `ecosystem/*/hero.jpg` | Same filenames, custom shots |

---

## 📅 BOSS-ONLY (date / contact stubs)

| # | Item | Today's value | Action |
|---|---|---|---|
| H | **Public phone number** | row hidden | Set `NEXT_PUBLIC_CONTACT_PHONE="+237…"` in `frontend/.env.production` |
| I | **Launch date "May 2026"** | hard-coded in 8 places | When date locks, search-replace across: `app/(site)/page.tsx`, `components/site/hero.tsx`, `app/(site)/about/page.tsx` (×3), `app/(site)/careers/page.tsx`, `app/(site)/ecosystem/page.tsx`, `app/(site)/partners/page.tsx`, `app/(site)/privacy/page.tsx`, `app/(site)/terms/page.tsx`, `lib/ecosystem.ts` |
| J | **"TBA" launch dates** | 88BASKET, O3MALL, QMEDIQ all say "TBA" | Update `launch:` field per product in `lib/ecosystem.ts` |
| K | **Per-product `websiteUrl`** | unused | Populate `websiteUrl` in `lib/ecosystem.ts` when product sites or app store listings exist; engineering adds outbound links |

---

## 🧪 BOSS-OWNED (QA gates that need real credentials)

These cannot be run end-to-end until the boss-only credentials above
are in place.

| # | Item | Depends on |
|---|---|---|
| L | E2E test: partner submission flow (validate → captcha → email → admin record) | #3 SMTP2GO + #5 hCaptcha |
| M | E2E test: contact form | #3 SMTP2GO + #5 hCaptcha |
| N | E2E test: job application incl. resume upload | #3 SMTP2GO + #5 hCaptcha |
| O | Admin 2FA enrolment dry run | #1 Postgres |
| P | Search functionality verification (`/search`) | #1 Postgres + seed data |
| Q | Lighthouse / Core Web Vitals on live URL | #2 Domain + Cloudflare (#6) |
| R | Cross-browser smoke (Chrome / Safari / Firefox / Edge) | live URL |
| S | First DB backup taken + restore drill rehearsed | #1 Postgres + #7 backup plan |

---

## 🛠 ENGINEERING follow-ups (not blockers; can ship after launch)

These are nice-to-have improvements engineering will pick up after
launch traffic stabilises.

| # | Item | Notes |
|---|---|---|
| T | **Promote CSP from Report-Only to enforce** | After ~30 days of clean reports, change the header name in `next.config.ts`. |
| U | **HSTS preload** | After 30 days of stable HTTPS, add `; preload` to the HSTS header and submit at https://hstspreload.org/. |
| V | **WebP exports for product PNG logos** | The 5 PNG logos (~200 KB each) would shrink ~70% as 512×512 WebP, improving LCP on `/ecosystem` cards. Boss can run them through Squoosh (free web tool) or ImageMagick. |
| W | **Quarterly restore drill** | Per `docs/RUNBOOK.md` §6.1 — run once #7 is in place; log result in `docs/RESTORE_DRILLS.md`. |
| X | **Office365 / Google OIDC for admin sign-in** | Currently password-only. SAML/OIDC reduces password attack surface. Roadmap, not blocker. |
| Y | **CI pipeline** | Lint + typecheck + alembic check in GitHub Actions on every PR. |

---

## 📌 What is NOT a remaining item

For absolute clarity, here is what was on prior lists and is now
**fully closed in code**:

- ✅ Light-only theme; dark/light toggle removed from navbar + admin
  topbar.
- ✅ All 7 products have dedicated pages with hero, overview, features,
  use cases, metrics, integrations, FAQ, related products.
- ✅ 5 of 7 product logos wired with real PNG artwork; brand-aligned
  hero gradients per product.
- ✅ Lint: 0 errors / 0 warnings (was 25 problems three sessions ago).
- ✅ Build: 55/55 pages prerendered, no errors.
- ✅ React 19 strict-effects fully compliant — `useSyncExternalStore`
  for storage hydration, refs assigned in effects (not during render),
  legitimate sync points use targeted `eslint-disable` only with
  rationale.
- ✅ SEO — per-product `Metadata`, Product JSON-LD with logo image,
  Organization JSON-LD, breadcrumb JSON-LD, sitemap, robots,
  OpenGraph + opengraph-image generation per route.
- ✅ Security headers — HSTS, X-Frame-Options, X-Content-Type-Options,
  Referrer-Policy, Permissions-Policy, X-DNS-Prefetch-Control, plus
  CSP in Report-Only mode.
- ✅ Domain consistency — every codepath uses `quatadigital.com` (no
  more legacy `quata.digital` references).
- ✅ Documentation — README production-deploy section, operational
  runbook, admin user manual all written.

---

## 🔁 How to use this doc

The order is **most-blocking → least-blocking**.

- Items 1–9 are launch-blockers and only the boss can resolve them.
- Items A–G are polish; site can launch without them but should not
  stay placeholder for long.
- Items H–K are content stubs that can ship and update later.
- Items L–S are QA gates that automatically unblock once 1–9 are
  done.
- Items T–Y are post-launch engineering polish.

When an item is resolved, delete its row from this file. When all of
1–9 are resolved, the site is ready for public launch.
