# Boss-only actions before public launch

Engineering has closed every dev-doable item. The list below is what only
the boss can complete — credentials, legal sign-off, brand assets, photos, or
a content decision.

For depth + audit IDs (`C##`/`H##`/`M##`), see [docs/PRODUCTION_AUDIT.md](docs/PRODUCTION_AUDIT.md).

Last reviewed: **2026-05-06**.

---

## Already resolved (no longer blocking)

- **Production Postgres URL** — already provisioned on the VPS. ✓
- **SMTP credentials** — already wired through the admin. ✓
- **Cloudflare** — descoped from launch blockers; revisit post-launch when traffic justifies edge caching.
- **Backup plan** — descoped; first backup work begins 3–4 weeks after launch once real usage is in the DB.

---

## 1. Domain canonicalisation ([C-02](docs/PRODUCTION_AUDIT.md#c-02))

Pick which host is the public URL: `quatadigital.com` (apex) or `www.quatadigital.com`. The other one will 301-redirect to it.

The DNS lives on Hostinger. Step-by-step walkthrough is in [docs/HOSTINGER_DOMAIN_CHECKLIST.md](docs/HOSTINGER_DOMAIN_CHECKLIST.md) — open that, walk through it, and send back what you see. Engineering then wires the redirect at the reverse proxy.

---

## 2. hCaptcha keys ([H-02](docs/PRODUCTION_AUDIT.md#h-02))

Create an account at https://hcaptcha.com (free), generate a site key + secret key, then paste both into:

**Admin → Settings → Integrations → hCaptcha**

(Engineering will ship the screen this sprint as part of the [F-01 settings store](docs/PRODUCTION_AUDIT.md#f-01).)

Currently the codebase reads keys from env vars and is a no-op when blank — so the keys can land any time without breaking anything else.

---

## 3. Sentry DSN ([H-03](docs/PRODUCTION_AUDIT.md#h-03))

Create a Sentry project at https://sentry.io (free for 5k errors/month), copy the DSN, paste into:

**Admin → Settings → Integrations → Sentry**

Same shape as #2. After saving, the backend needs a restart for the SDK to actually initialise — the admin form will say so.

---

## 4. Privacy & terms — verify with lawyer ([M-01](docs/PRODUCTION_AUDIT.md#m-01))

Engineering will write the long-form draft for `/privacy` and `/terms` and publish them as CMS-managed pages. Once the draft is in admin, send the URLs to a Cameroonian lawyer for a Loi n° 2010/012 review and edit inline through the admin panel based on what they say.

Also confirm `privacy@quatadigital.com` is monitored (or pick a different mailbox).

---

## 5. Content & images — uploaded from admin

Once the new CMS lands ([F-02](docs/PRODUCTION_AUDIT.md#f-02)), all content + image updates flow through the admin panel:

| What | Where | Notes |
|---|---|---|
| Founder photo | Admin → Pages → About → Hero section | High-res JPG, ≥ 800×1000. |
| QUATAPAY dashboard screenshot | Admin → Products → quatapay → Hero | Real dashboard, not gradient. |
| ABAQWA dashboard screenshot | Admin → Products → abaqwa → Hero | Same. |
| Real 88BASKET logo | Admin → Products → 88basket → Logo | Replaces placeholder SVG. |
| Real QMEDIQ logo | Admin → Products → qmediq → Logo | Same. |
| Partner / press logos | Admin → Pages → Home → Press strip | Only logos with explicit permission. |
| Per-product launch dates / website URL | Admin → Products → {slug} | "TBA" today for 88BASKET, O3MALL, QMEDIQ. |
| Public phone | Admin → Settings → Contact info | Hidden in footer until set. |
| Lock the launch date copy | Admin → Pages (Home, About, Ecosystem, …) | Search-and-replace "May 2026" once locked. |
| Privacy / Terms text | Admin → Pages → Privacy / Terms | Lawyer-edited. |

---

## 6. Newsletter

Engineering will ship an admin compose-and-send screen ([M-02](docs/PRODUCTION_AUDIT.md#m-02)) — broadcast directly from the admin to every active subscriber. **No third-party ESP sync** unless you change your mind later.

Subscribers list, CSV export, and unsubscribe are already live at `/admin/newsletter`.

---

## How to use this doc

When you can answer one of the items above, paste the value into the relevant
admin screen (or the relevant `.env` for items still env-driven). Items are
independent.

Top priority for unblocking launch is **#1 (domain)** — it's what stops the
apex/www inconsistency that will cost SEO and break sign-ins from the wrong host.
