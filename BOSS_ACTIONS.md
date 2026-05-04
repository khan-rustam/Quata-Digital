# Boss-only actions before public launch

Engineering closed every dev-doable item across the audit. This document lists
the remaining items that **only the boss can complete**, the exact handoff each
one needs, and where in the codebase the integration is already wired up
waiting for the value.

The order roughly matches launch sequencing — top items unblock the most
downstream work.

---

## 1. Pick the production database (audit C12)

**What I need from you:** A managed Postgres URL (Neon, Supabase, Railway,
DigitalOcean, RDS — any of them).

**Where it goes:** `DATABASE_URL` in the production `.env` of the backend
container. Everything else is wired:
- The Alembic baseline migration
  ([backend/alembic/versions/df03f53e48ce_initial_baseline.py](backend/alembic/versions/df03f53e48ce_initial_baseline.py))
  builds all 21 tables on a fresh DB.
- The production-config guard refuses boot until you set `AUTO_CREATE_TABLES=false`,
  which forces the deploy script to run `alembic upgrade head` instead.

---

## 2. Confirm the production domain (audit H7, indirectly)

**What I need from you:** Decide whether `quatadigital.com` (apex) or
`www.quatadigital.com` is canonical, and which one redirects to the other.

**Where it goes:** DNS (apex A/AAAA + `www` CNAME) and the Cloudflare
page rule that does the redirect.

---

## 3. SMTP2GO credentials (audit H1)

**What I need from you:** The SMTP2GO username, password, and confirmed
sender domain (with SPF, DKIM, DMARC verified inside SMTP2GO).

**Where it goes:**

```
EMAIL_BACKEND=smtp
SMTP_HOST=mail.smtp2go.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USER=<from SMTP2GO>
SMTP_PASSWORD=<from SMTP2GO>
EMAIL_FROM=QUATA Digital <noreply@quatadigital.com>
EMAIL_NOTIFY_TO=info@quatadigital.com
```

The production-config guard will refuse to boot until `EMAIL_BACKEND` is
no longer `console`.

Already wired:
- Partner submissions, contact form, job applications, password resets,
  staff invites all go through `app/services/email.py` already.

---

## 4. Sentry DSN (audit H13)

**What I need from you:** A Sentry account + DSN, or a definitive
"we're skipping Sentry — use BugSnag/Rollbar instead."

**Where it goes:**

```
SENTRY_DSN=<from sentry.io>
SENTRY_ENV=production
```

Already wired in `app/core/logging_config.configure_sentry()`. Without a
DSN it's a no-op.

---

## 5. hCaptcha keys (audit H5)

**What I need from you:** A site key + secret from hcaptcha.com (free
tier is fine for launch volume).

**Where it goes:**

Backend `.env`:
```
HCAPTCHA_SITE_KEY=<public site key>
HCAPTCHA_SECRET_KEY=<server secret>
```

Frontend `.env`:
```
NEXT_PUBLIC_HCAPTCHA_SITE_KEY=<same public site key>
```

Already wired:
- Public partner submit, contact form, job application, newsletter
  signup all read the token from the form and ship it to the server.
- `app/services/captcha.py` validates the token against hCaptcha when
  the keys are present, no-ops when they aren't.

---

## 6. Cloudflare account (audit H7)

**What I need from you:** Cloudflare account with the apex domain proxied
through it. Once it's there I'll add the cache rules + page rules.

---

## 7. Backup plan + retention policy (audit H8)

**What I need from you:** Three answers — frequency (daily? hourly?),
retention (7 / 30 / 90 days?), and where backups live (managed Postgres
provider's default, or off to a separate bucket).

I'll then write the script + document the documented restore drill.

---

## 8. Legal review of `/privacy` and `/terms` (audit M11, M12)

**What I need from you:**
- Sign-off (or red-line edits) from a Cameroonian lawyer on the current
  `/privacy` and `/terms` text against Loi n° 2010/012.
- Confirmation that `privacy@quatadigital.com` exists and is monitored.

---

## 9. Newsletter ESP decision (audit C2)

**What I need from you:** Either:
- "Keep the in-DB list" — already shipped, admin can export CSV from
  `/admin/newsletter` and send broadcasts manually; or
- "Sync to Mailchimp / ConvertKit / Buttondown" — give me the API key
  and I'll wire the sync.

---

## 10. Founder photo + product screenshots (audit M1, M2)

**What I need from you:**
- A high-res headshot of Neba Clovis Ngwa to replace the placeholder on
  `/about`.
- Screenshots of QUATAPAY and ABAQWA dashboards to replace the gradients
  on `/ecosystem/quatapay` and `/ecosystem/abaqwa`.

Drop them in `frontend/public/` and tell me what to call them — I'll
swap the `<Image>` tags.

---

## 11. Press / partner logos (audit M7)

**What I need from you:** Permission to display any partner or press
logos. Until then, the site has no logo wall — which is correct because
fake logos are worse than no logos.

---

## 12. Launch date (audit boss-only #10)

**What I need from you:** Lock the launch date. The site copy currently
says May 2026 in several places (founder bio, blog posts, ecosystem
page). When the date firms up, search-and-replace.

---

## How to use this doc

When you can answer one of the items above, paste the value into the
relevant `.env` (or send me the asset). Each item is independent — you
don't need them in this order. Items 1, 3, and 5 are the highest-impact
because they unblock the production-safety guards.

Audit cross-references are to the original [PRODUCTION_AUDIT.md](PRODUCTION_AUDIT.md).
