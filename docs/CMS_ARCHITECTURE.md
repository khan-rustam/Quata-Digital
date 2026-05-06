# CMS architecture — two systems, on purpose

**TL;DR:** every public marketing page renders from the CMS first
(`PageContent` model + `<SectionRenderer />`) and falls back to its
existing static React copy when the page is unpublished or the API is
down. The legacy `Product` model is kept for ecosystem-card metadata
that's not section-shaped (logo, accent colour, status badge).

---

## The two systems

| System | Model | What it stores | Edited at |
|---|---|---|---|
| **CMS section editor** (new) | `PageContent` | Full page bodies as ordered, typed sections | `/admin/cms/pages/{slug}` |
| **Legacy CRUD** (existing) | `Product`, `Page`, blog `BlogPost` | Lightweight metadata records (slug, name, tagline, status, logo) | `/admin/products`, `/admin/cms` |

They are **deliberately not migrated into one**. Each has a different
shape and a different editing workflow.

## Per-product pages: how they actually render

The public route `/ecosystem/{slug}/page.tsx` does:

```tsx
const cms = await getPageContent(`ecosystem/${slug}`);
if (cms) return <SectionRenderer sections={cms.sections} />;
// else: fall back to the legacy product page driven by the Product model
return <LegacyProductPage product={getProduct(slug)} />;
```

So the rendering path depends on whether the boss has **published** the
CMS version of that page in admin:

- **Unpublished CMS page** → public site renders from the legacy
  `Product` model (current behaviour, unchanged from before the CMS
  shipped).
- **Published CMS page** → public site renders the section list. The
  ecosystem-index card on `/ecosystem` still pulls product metadata
  (name, tagline, status badge, logo) from the `Product` model — that
  isn't section-shaped data, so it stays where it is.

Same wiring applies to `/partners/{type}/page.tsx`.

## Why we kept both

Two reasons:

1. **The Product / Partner index cards aren't section-shaped.** Each
   ecosystem card on `/ecosystem` shows a logo, status pill, accent
   colour, and short tagline. Forcing that into a "section" is more
   awkward than just keeping a `Product` row.
2. **Zero-downtime cutover.** The boss can publish CMS pages one at a
   time without breaking the rest. Migrating everything to the CMS in
   one go would force a flag-day.

## When to use which

| You want to… | Edit here |
|---|---|
| Change a product's status badge or accent colour | `/admin/products` |
| Update the product's homepage hero, features list, FAQ, CTAs | `/admin/cms/pages/ecosystem/{slug}` |
| Add a new product to the ecosystem | `/admin/products` (creates the index card) → `/admin/cms/pages/ecosystem/{slug}` (build the body) |
| Change the partner-application form fields | code change — the forms in `/components/forms/` are React components |
| Change the marketing copy around the form | `/admin/cms/pages/partners/{type}` |

## Sidebar shortcut

The Products admin (`/admin/products`) shows a "Edit page" link next to
each product, jumping straight to the matching CMS section editor. Same
on Partners (where applicable). This means the boss never has to think
about which system they're in — they pick the product, click "Edit
page", and they're in the right place.

## Migration path (if we ever want one)

Should we ever decide to fully unify, the path is:

1. Add a `legacy_card` section type that wraps Product fields (logo,
   status, accent).
2. For each Product row, pre-seed an ecosystem/{slug} page that starts
   with that section + whatever else.
3. Drop `Product` reads from the public `/ecosystem/[slug]` and index
   pages.
4. Decommission `/admin/products`.

Not recommended unless we hit a concrete ergonomics problem. The
current dual-system maps cleanly to the two real workflows.
