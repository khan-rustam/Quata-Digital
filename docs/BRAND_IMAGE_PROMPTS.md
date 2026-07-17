# QUATA Digital — image generation prompts (ChatGPT / DALL·E)

Prompts for generating OG cards and marketing imagery that match the QD brand.
Colours below are **sampled from the real logo artwork** (`frontend/brand/mark.png`),
so they are the ground truth — not approximations.

---

## ⚠️ Read this first: never let AI draw the logo

Image models **cannot reproduce a logo accurately**. Ask ChatGPT to draw the QD
mark or the "QUATA DIGITAL" wordmark and it will hand back a warped monogram
with misspelled or melted letters — every time, no matter how good the prompt.
The tagline ("CONNECTING LIFE. POWERING POSSIBILITIES.") is small text and comes
back as gibberish.

**So use this two-step method:**

1. **Generate the background/scene only** — explicitly tell it to leave empty
   space and draw **no text and no logo**.
2. **Composite the real logo on top** yourself — in Figma/Canva, drop
   `frontend/brand/header-lockup.png` into the clear space, and set the
   headline in real type.

Every prompt below is written for step 1. The `[LEAVE CLEAR]` instructions are
load-bearing — keep them in.

> **The site already does step 2 for you.** `lib/og-template.tsx` composites the
> real lockup and real type over these backgrounds at build time, so the logo
> and headline are always pixel-crisp and the copy always matches the CMS. You
> only ever need to supply the background.

### Backgrounds currently wired in

| Master | Renders to | Used by |
|---|---|---|
| `frontend/brand/og/home.png` | `public/brand/og/home.jpg` | `/` homepage card |
| `frontend/brand/og/blog.png` | `public/brand/og/blog.jpg` | every blog post card |
| `frontend/brand/og/careers.png` | `public/brand/og/careers.jpg` | every job post card |

To swap one: generate a replacement with the matching prompt below, drop it in
`frontend/brand/og/<name>.png`, and run `node scripts/generate-favicons.mjs`.
It is resized to exactly 1200×630 and encoded as JPEG automatically.

`frontend/brand/social/` holds artwork that is **not** used by the site (social
posts, deck slides, ads). Nothing renders it and it is never served.

---

## Block A — paste this first, in a new chat

```
You are designing brand imagery for QUATA Digital, a Cameroon-based technology
company building Africa's connected digital ecosystem (payments, business
operations and commerce on one rail).

BRAND PALETTE — use these exact hex values, no other colours:
  Deep navy-teal   #003048   (darkest; backgrounds, depth)
  Brand teal       #006078   (primary; the anchor colour)
  Core teal        #0090A8   (the logo's signature teal)
  Bright cyan      #00D8F0   (highlights, glows, energy)
  Gold             #E8B14A   (the ONLY accent — use sparingly, ~5% of the frame)
  Warm gold-lit    #FFC030   (gold highlights only)
  Ink              #0F1216   (near-black backgrounds)
  Off-white        #FAFAF7   (light backgrounds)

PALETTE RULES:
- Teal and gold are the whole identity. Never introduce green, purple, red,
  orange or pink. The company logo is a teal "Q" interlocked with a gold "D" —
  those two colours must stay the heroes.
- Gold is an accent, never a background. Teal dominates.
- Keep gradients within the teal ramp (#003048 -> #006078 -> #0090A8 -> #00D8F0).

STYLE:
- Modern fintech / enterprise-infrastructure. Premium, restrained, confident.
- Clean geometry, generous negative space, soft depth. Think Stripe or Linear,
  not a stock-photo collage.
- Subtle metallic sheen is on-brand (the logo is glossy/metallic).
- African context where people or places appear: Central/West African subjects,
  contemporary urban Cameroon, real professional settings. Never stereotypes,
  never poverty framing, never generic "Africa" iconography (no acacia trees,
  no sunset silhouettes, no tribal patterns).

HARD RULES:
- Render NO text, NO letters, NO numbers, NO logos, NO wordmarks anywhere.
  I composite real type and the real logo myself afterwards.
- No watermarks, no UI chrome, no borders/frames.
- Photorealistic OR clean vector-illustration — never a mix of both.

Confirm you understand, then wait for my image request.
```

---

## Block B — the image request

Send one of these **after** Block A.

### B1 · Default OG / link-preview card (1200×630)

```
Create a 1200x630 landscape image (1.91:1, this exact ratio).

Composition: an abstract representation of connected financial infrastructure —
softly glowing nodes joined by clean flowing lines, suggesting value moving
across a network. Deep teal (#003048) in the top-left falling to brand teal
(#006078) and core teal (#0090A8) toward the bottom-right. A few bright cyan
(#00D8F0) highlights where lines meet. One or two restrained gold (#E8B14A)
accent nodes. Subtle dark vignette at the edges.

[LEAVE CLEAR] The left 60% of the frame must stay visually quiet and
uncluttered — I place a logo and a headline there. Push all detail to the
right third and the far edges. No focal point in the left-centre.

No text, no letters, no logo. 1200x630.
```

### B2 · Blog / editorial card (1200×630)

```
Create a 1200x630 landscape image (1.91:1).

Composition: an abstract editorial texture — layered translucent planes and
thin flowing contour lines, like a topographic map of a network. Dark ink
(#0F1216) base moving into deep navy-teal (#003048) and brand teal (#006078).
Faint bright cyan (#00D8F0) rim-light along a few contours. No gold, or one
single gold thread at most. Quiet, sophisticated, low contrast.

[LEAVE CLEAR] Keep the left 60% calm and near-empty for a logo and headline.

No text, no letters, no logo. 1200x630.
```

### B3 · Careers / people card (1200×630)

```
Create a 1200x630 landscape photograph (1.91:1).

Subject: two or three Black African professionals collaborating in a bright
modern office in Cameroon — laptops, a whiteboard, natural window light. Warm,
candid, genuinely engaged; not posed stock-photo smiling at camera. Shallow
depth of field.

Colour: grade toward teal — cool teal shadows (#006078), a warm gold (#E8B14A)
window highlight. The teal/gold relationship should be visible but natural.

[LEAVE CLEAR] Frame the subjects in the RIGHT half. The left 45% should be a
clean, softly out-of-focus wall or window light — I place a logo and headline
there.

No text, no letters, no logo, no watermark. 1200x630.
```

### B4 · Product / feature illustration (square or 16:9)

```
Create a 1600x900 clean vector illustration (16:9).

Subject: [DESCRIBE THE PRODUCT — e.g. "a mobile money transfer moving between
two phones", "a merchant dashboard showing orders", "a delivery route across a
city"].

Style: flat geometric vector with soft layered depth, rounded corners,
generous negative space, centred composition on an off-white (#FAFAF7)
background. Teal ramp (#006078 / #0090A8 / #00D8F0) for primary shapes, gold
(#E8B14A) for exactly one focal accent. Thin consistent line weights.

No text, no letters, no numbers on any screen or label, no logo. 1600x900.
```

### B5 · Social post background (1080×1080)

```
Create a 1080x1080 square image.

Composition: a premium abstract gradient mesh in the teal ramp — deep navy-teal
(#003048) through brand teal (#006078) to core teal (#0090A8), with a bright
cyan (#00D8F0) bloom in one corner and a fine metallic gold (#E8B14A) hairline
arc as the only accent. Soft grain. Lots of open space.

[LEAVE CLEAR] The centre 70% must stay quiet — logo and copy go there.

No text, no letters, no logo. 1080x1080.
```

---

## Block C — compositing the real logo

**Skip this for the three OG backgrounds above — the site composites those in
code.** This is for artwork you finish by hand: social posts, decks, ads.

After the AI returns the background:

| Slot | Asset | Notes |
|---|---|---|
| Any card ≥ 600px wide | `frontend/brand/header-lockup.png` | Full lockup with tagline |
| Small / square / tight | `frontend/brand/mark.png` | QD monogram only — the tagline is unreadable below ~200px wide |
| Square or portrait slot | `frontend/brand/stacked-lockup.png` | Mark above wordmark |

Rules of thumb:

- **Clear space** — keep at least the height of the QD monogram empty on all
  sides of the lockup.
- **Size** — on a 1200×630 card, the lockup reads well at ~320px wide.
- **Placement** — top-left, on a quiet part of the background.
- **Contrast** — the artwork carries its own teal and gold, so it reads on both
  near-white (#FAFAF7) and ink (#0F1216). It does **not** read on mid-teal:
  never place it on #0090A8, the teal wordmark disappears into it.
- **Photos need a scrim.** This bit is not optional and it is the one that
  catches people out. A photographic background looks dark but rarely *is* —
  the careers photo's "empty" left wall measured bright enough that white text
  scored **1.77:1**, far below the 4.5:1 minimum. Lay a dark gradient over the
  text column first (the site uses black at 94% fading to 14% left-to-right,
  which lifted it to 6.6:1). Abstract dark backgrounds usually don't need one.
- **Never** recolour, outline, rotate, add a drop shadow to, or squash the
  lockup. Scale proportionally only.
- Headline type: any clean geometric sans (the site uses **Geist**). White on
  dark backgrounds, `#0F1216` on light ones.

---

## Block D — quick fixes

| Problem | Say this |
|---|---|
| Colours drifted green/blue | "The teal is wrong. Use exactly #006078 and #0090A8. No green." |
| Too much gold | "Reduce gold to a single small accent, under 5% of the frame. Teal dominates." |
| It drew text/a logo anyway | "Remove all text and logos. The image must be pure background." |
| Left side too busy | "The left 60% must be empty and calm. Move all detail to the right edge." |
| Looks like generic stock | "More restrained and geometric. Premium fintech, like Stripe. Less decoration." |
| Wrong aspect ratio | "Regenerate at exactly 1200x630 pixels, 1.91:1 landscape." |

---

## Reference — where the colours come from

Sampled from the logo, with WCAG contrast against white:

| Hex | Role | On white | Safe for text? |
|---|---|---|---|
| `#003048` | Deepest | 13.85:1 | Yes |
| `#006078` | **Brand / primary** | 7.13:1 | Yes (AAA) |
| `#0090A8` | Core logo teal | 3.78:1 | **No** — large graphics only |
| `#00D8F0` | Highlight | 1.74:1 | **No** — decorative only |
| `#E8B14A` | Gold accent | 1.94:1 | **No** — decorative only |

This is why the site's primary colour is `#006078` and not the logo's more
prominent `#0090A8`: white text on `#0090A8` fails accessibility. If you make
artwork with dark text, keep it on `#FAFAF7`; light text goes on `#003048` or
`#006078`.
