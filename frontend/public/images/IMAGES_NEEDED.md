# Images — drop-in manifest

Every slot below is wired into the site via `<BrandImage>`. Right now each
slot has a **stopgap placeholder photo** (random-but-unique, from
picsum.photos) so the page never looks empty. Those placeholders are NOT
on-brand — they're nature/landscape shots, not African business scenes.

Your job: open the Unsplash search link for each slot, pick a photo you
like, **download it, rename it to the exact filename below, and save it at
the path shown**. The site picks it up on next refresh.

---

## How to download from Unsplash

1. Click the Unsplash search link in the table.
2. Pick a photo whose vibe matches the description.
3. Click **Download free** → choose **Large** (or **Original** for hero
   images).
4. **Rename** the downloaded file to match the **filename** column below.
5. Save it under `frontend/public/images/...` at the **path** column.
6. Refresh the relevant page in the browser. Done.

> No code changes needed. The page already references that exact path.

---

## Boss guidance

> "Stock images acceptable for the start. Mostly African inclined in
> terms of people's images they should be blacks; other images can be
> global, no problem."  — Boss, question 2.7

So: every photo with **people** should feature Black/African subjects.
Photos of dashboards, products, food, real-estate, etc. can be global.

---

## About — `frontend/public/images/about/`

| Filename       | Aspect (W × H) | Vibe / who's in it                                              | Unsplash search                                                                 |
|----------------|----------------|------------------------------------------------------------------|---------------------------------------------------------------------------------|
| `hero.jpg`     | 1200 × 1000    | African team in a modern startup office, daylight, collaborative | <https://unsplash.com/s/photos/african-startup-team>                            |
| `founder.jpg`  | 640 × 800      | Confident African male portrait, 30s–40s, smart-casual or suit, plain background | <https://unsplash.com/s/photos/african-businessman-portrait>      |

---

## Careers — `frontend/public/images/careers/`

| Filename     | Aspect (W × H) | Vibe / who's in it                                                              | Unsplash search                                                |
|--------------|----------------|----------------------------------------------------------------------------------|----------------------------------------------------------------|
| `hero.jpg`   | 1200 × 1000    | Diverse African team at work — laptops, whiteboard, energy. Different shot from About. | <https://unsplash.com/s/photos/african-tech-team-office> |

---

## Partners — Business · `frontend/public/images/partners/business/`

| Filename       | Aspect      | Vibe                                                                              | Unsplash search                                                       |
|----------------|-------------|-----------------------------------------------------------------------------------|-----------------------------------------------------------------------|
| `hero.jpg`     | 1200 × 900  | African shop owner / merchant accepting a mobile-money or card payment            | <https://unsplash.com/s/photos/african-merchant-shop>                 |
| `sidebar.jpg`  | 800 × 600   | Close-up of a card reader, POS terminal or phone payment                          | <https://unsplash.com/s/photos/payment-terminal>                      |
| `faq.jpg`      | 900 × 1100  | African businesswoman on a phone in her shop or office (portrait orientation)     | <https://unsplash.com/s/photos/african-businesswoman-phone>           |

---

## Partners — Strategic · `frontend/public/images/partners/strategic/`

| Filename       | Aspect      | Vibe                                                                              | Unsplash search                                                       |
|----------------|-------------|-----------------------------------------------------------------------------------|-----------------------------------------------------------------------|
| `hero.jpg`     | 1200 × 900  | African executives in a boardroom, handshake, or signing a deal                   | <https://unsplash.com/s/photos/african-executive-boardroom>           |
| `sidebar.jpg`  | 800 × 600   | Two professionals in a meeting — over a laptop or document                        | <https://unsplash.com/s/photos/business-meeting-handshake>            |
| `faq.jpg`      | 900 × 1100  | African executive in a suit, leadership pose, portrait orientation                | <https://unsplash.com/s/photos/african-ceo-portrait>                  |

---

## Partners — Investor · `frontend/public/images/partners/investor/`

| Filename       | Aspect      | Vibe                                                                              | Unsplash search                                                       |
|----------------|-------------|-----------------------------------------------------------------------------------|-----------------------------------------------------------------------|
| `hero.jpg`     | 1200 × 900  | Charts / financial dashboard / growth graph (no people needed — global is fine)   | <https://unsplash.com/s/photos/financial-dashboard-charts>            |
| `sidebar.jpg`  | 800 × 600   | Laptop showing analytics or stock data, clean shot                                | <https://unsplash.com/s/photos/laptop-analytics>                      |
| `faq.jpg`      | 900 × 1100  | Confident African woman professional, portrait, business setting                  | <https://unsplash.com/s/photos/african-businesswoman-confident>       |

---

## Partners — Service · `frontend/public/images/partners/service/`

| Filename       | Aspect      | Vibe                                                                              | Unsplash search                                                       |
|----------------|-------------|-----------------------------------------------------------------------------------|-----------------------------------------------------------------------|
| `hero.jpg`     | 1200 × 900  | African delivery rider on a motorcycle / scooter, branded gear if possible        | <https://unsplash.com/s/photos/africa-delivery-rider>                 |
| `sidebar.jpg`  | 800 × 600   | Developer at a laptop, hands-on-keyboard. African if available, global is OK.     | <https://unsplash.com/s/photos/african-developer-laptop>              |
| `faq.jpg`      | 900 × 1100  | African engineer / freelancer at a desk, portrait orientation                     | <https://unsplash.com/s/photos/african-engineer-desk>                 |

---

## Ecosystem — `frontend/public/images/ecosystem/{slug}/hero.jpg`

Single hero per product. Either a UI mockup (when you have one) or a
contextual photo of the use case.

| Slug         | Vibe                                                                                              | Unsplash search                                                          |
|--------------|---------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------|
| `quatapay`   | Mobile phone showing a payment / mobile-money screen, African hand holding it                     | <https://unsplash.com/s/photos/mobile-money-africa>                      |
| `abaqwa`     | Laptop dashboard / inventory screen, modern, clean. People optional.                              | <https://unsplash.com/s/photos/business-dashboard-laptop>                |
| `quatafood`  | African food prep / restaurant kitchen / delivery rider with food bag                             | <https://unsplash.com/s/photos/african-food-delivery>                    |
| `88basket`   | Modern shopping bags / grocery delivery / African market reimagined                               | <https://unsplash.com/s/photos/online-shopping-bags>                     |
| `88brickz`   | Modern African house exterior / contemporary real-estate architecture                             | <https://unsplash.com/s/photos/modern-african-architecture>              |
| `o3mall`     | Modern shopping mall storefront / commerce center                                                 | <https://unsplash.com/s/photos/modern-shopping-mall>                     |
| `qmediq`     | African doctor in a clinic with stethoscope or patient consultation                               | <https://unsplash.com/s/photos/african-doctor-clinic>                    |

All ecosystem heroes: **1200 × 900** (4:3 landscape). Filename always
`hero.jpg` inside the slug folder.

---

## File specs (reference)

- **Format:** JPG. PNG only if you specifically need transparency.
- **Quality:** export at the dimensions above or 2× for retina; then
  optimise via [TinyPNG](https://tinypng.com) or [Squoosh](https://squoosh.app).
- **Target file size:** under 250 KB per image. Hero shots can go up to
  400 KB if the image needs the detail.

---

## Re-running the auto-fetcher

If you ever delete an image and want the site to fall back to a
placeholder again, run:

```
python scripts/fetch_images.py
```

It only fetches **missing** files — it will never overwrite a real photo
you've placed manually. Use `--force` if you want to re-roll the
placeholders.
