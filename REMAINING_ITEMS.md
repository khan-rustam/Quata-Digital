# QUATA Digital — Launch readiness dashboard

Single-page status board. For depth, see:
- [docs/PRODUCTION_AUDIT.md](docs/PRODUCTION_AUDIT.md) — numbered audit (`C##`/`H##`/`M##`/`F##`).
- [BOSS_ACTIONS.md](BOSS_ACTIONS.md) — boss-only blockers.
- [docs/HOSTINGER_DOMAIN_CHECKLIST.md](docs/HOSTINGER_DOMAIN_CHECKLIST.md) — step-by-step DNS check.
- [docs/RUNBOOK.md](docs/RUNBOOK.md) — on-call / deploy / rollback.

Last reviewed: **2026-05-06** · Backend `0.3.0` · Frontend `Next.js 16.2.4 / React 19.2.4`.

---

## Status

- ✅ **All engineering sprint items closed** — F-01, F-02, F-03, F-04, M-02 are shipped, lint clean, build green.
- 🚧 **Boss-blocked** items remain — credentials, lawyer review, brand assets.

The site already serves correctly with zero CMS sections published — every page falls back to the existing static React copy. As the boss publishes pages in admin, they progressively switch to CMS-driven rendering with no downtime.

---

## ✅ Shipped this sprint

| Phase | Surface |
|---|---|
| F-01 Site settings store | `SiteSetting` model, 15 keys across 4 groups, public read + admin CRUD APIs, `/admin/site-settings` UI with Integrations / Contact / Social / Toggles tabs, masked secrets with reveal/replace UX, **SMTP test-send button** with live result feedback. |
| F-02 CMS for marketing pages | `PageContent` model with 14-type discriminated-union schema (Pydantic); 20 pages auto-seeded; `/admin/cms/pages` list + `/admin/cms/pages/[slug]` editor with drag-reorder, hide/show, per-section slide-over forms; image upload in every form; `<SectionRenderer />` rendering all 14 types; **all 11 public pages wired with API-first → static fallback**; **9 pages pre-seeded with starter sections** matching the current static copy so the boss has a starting point to edit. |
| F-03 Markdown editor polish | `<MarkdownEditor>` with toolbar (H2/H3, Bold, Italic, Inline code, Lists, Blockquote, Link, Image upload), three-mode preview (Write / Split / Preview), wired into blog posts, CMS pages, and newsletter compose. |
| F-04 Frontend chrome polish | Modern 404 with home/back/support/search links, branded `loading.tsx` for site + admin, audited error pages. |
| M-02 Newsletter broadcast | `NewsletterBroadcast` audit model + admin compose UI at `/admin/newsletter/broadcast` with subject + markdown body, "Send a test first" panel, send-to-all gated by confirm dialog, history feed with delivered/failed counts. |

---

## 🚨 Boss-blocked (cannot launch publicly without)

| # | Item | Audit ID | Notes |
|---|---|---|---|
| 1 | Domain canonicalisation — Hostinger DNS | [C-02](docs/PRODUCTION_AUDIT.md#c-02) | Walk through [HOSTINGER_DOMAIN_CHECKLIST.md](docs/HOSTINGER_DOMAIN_CHECKLIST.md) and send results. |
| 2 | hCaptcha keys | [H-02](docs/PRODUCTION_AUDIT.md#h-02) | Paste into **Admin → Site settings → Integrations**. |
| 3 | Sentry DSN | [H-03](docs/PRODUCTION_AUDIT.md#h-03) | Same panel. Backend restart required to apply. |
| 4 | Lawyer review of `/privacy` + `/terms` | [M-01](docs/PRODUCTION_AUDIT.md#m-01) | Pre-seeded draft already published-ready in admin — open the page, copy the URL, send to lawyer. |
| 5 | Founder photo + product screenshots + 88BASKET / QMEDIQ logos | M-03..M-06 | Upload through admin (per-section image upload in CMS, or via `/admin/products`). |
| 6 | Public phone, address, social links | M-08 | Set in **Admin → Site settings → Contact info / Social**. |
| 7 | Lock the launch date | M-07 | Edit the Hero section on Home → About in admin once date firms up. |
| 8 | Per-product launch dates + websiteUrl | M-09, M-10 | Through `/admin/products` (legacy product CRUD) — extending to per-product CMS is a future task. |

---

## 🛠 Post-launch follow-ups (not blockers)

| # | Item | Notes |
|---|---|---|
| T | Promote CSP from Report-Only to enforce | After ~30 days of clean reports. |
| U | HSTS preload | After 30 days of stable HTTPS. |
| V | First DB backup + restore drill | 3–4 weeks post-launch. |
| W | Cloudflare in front of apex | When traffic justifies. |
| X | OIDC / SSO for admin sign-in | Reduces password attack surface. |
| Y | CI pipeline (lint + typecheck + alembic check) | GitHub Actions on every PR. |
| Z | Redis-backed WebSocket hub | Only when scaling beyond a single uvicorn worker. |
| AA | Per-product CMS pages | Currently the 7 product pages render from the legacy `Product` model. Migrating them to section-based PageContent is the natural next sprint. |
| AB | Per-partner-type CMS pages | Same shape as AA — ready in the schema, just needs section pre-seeding + frontend integration. |
| AC | TipTap block editor for blog | Option B from the original plan. Markdown + toolbar (current) covers ~90% of use cases. |

---

## How to use this doc

Order is **most-blocking → least-blocking**. Items 1–8 are what stop public
launch; items T–AC are post-launch engineering polish. The site can launch
with item 1 + 2 + 6 done; everything else can land in the days after launch.

After deploy, every boss-blocked item is editable through the admin panel —
no code change needed.
