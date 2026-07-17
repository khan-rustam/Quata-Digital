# Imagery — now custom on-brand illustrations (no photos needed)

> **This site no longer uses stock/placeholder photos for its marketing pages.**
> Every page/section image is a built-in, custom **SVG illustration** rendered
> in code — orange `#FF6B00` + Quata blue — so the visual always matches the
> content and loads instantly. The old `picsum` placeholder photos were removed.

## Where the illustrations live

`frontend/components/site/illustrations/`

- `palette.ts` — the orange + blue colour tokens
- `kit.tsx` — reusable SVG primitives (cards, charts, phone, person, icons…)
- `illustration.tsx` — the `<Illustration name=… />` wrapper + registry (name → artwork)
- domain files: `payments.tsx`, `logistics.tsx`, `food.tsx`, `commerce.tsx`,
  `realestate.tsx`, `health.tsx`, `analytics.tsx`, `people.tsx`, `editorial.tsx`

Pages render artwork by **name**, e.g. `<Illustration name="product-quatapay" … />`.
Registered names cover: About (hero, founder), Careers (hero), Contact (hero,
office), Partners business/strategic/investor/service (hero, sidebar, faq), and
all 7 products (`product-<slug>`). Product feature cards pick a relevant icon via
`lib/feature-icons.ts`.

## Blog / news covers

Article covers come from `components/site/illustrations/editorial.tsx`
(`<PostCover category=… />`), themed per category. If a post sets
`cover_image_url` in the CMS, that uploaded image is used instead.

## Want to change an illustration?

Edit the matching component in the domain file (it's plain SVG + the kit). To add
a new slot, create/extend a component and add it to the registry in
`illustration.tsx`. No image files to source, rename, compress, or upload.

## Logos

Product logos still live as real files under `public/ecosystem/logos/`.

The **QUATA Digital** brand marks are generated, not hand-placed. The masters
live in `frontend/brand/` (outside `public/`, so the multi-megabyte originals
are never served) and `scripts/generate-favicons.mjs` renders every derivative
from them:

- `brand/mark.png` — the QD monogram → favicon, app icons, maskable PWA icons
- `brand/header-lockup.png` → `public/brand/lockup.png`, used by the navbar,
  footer and both OG variants
- `brand/og/{home,blog,careers}.png` → `public/brand/og/*.jpg`, the OG card
  backgrounds. These are backgrounds **only** — `lib/og-template.tsx` draws the
  real lockup and real type over them, so no logo or text is ever baked in
- `brand/social/` — deck/ad/social artwork. Nothing renders it; never served

Re-run `node scripts/generate-favicons.mjs` after changing a master. Don't edit
anything under `public/brand/` by hand; it will be overwritten. See
`docs/BRAND_IMAGE_PROMPTS.md` for generating new background artwork.
