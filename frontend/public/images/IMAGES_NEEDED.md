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

Brand/product logos still live as real files under `public/ecosystem/logos/` and
`public/logo.png` — those are unchanged.
