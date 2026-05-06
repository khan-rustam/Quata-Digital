# QUATA Digital — Open content questions

Most of the original intake questionnaire has been answered and reflected in
the seed data ([backend/app/seeds/seed.py](../backend/app/seeds/seed.py)) and
the marketing copy in `frontend/app/(site)/`. What remains is content the
engineering team genuinely cannot infer.

> When you have answers, paste them in this file (or send a doc keyed to the
> section numbers) and engineering will wire them into the right pages.

Last reviewed: **2026-05-06**.

---

## 1. Per-product real-world numbers

For each product where a real metric exists, send:

- **QUATAPAY** — pilot transaction count, settlement window (T+0 / T+1?), supported networks confirmed (MTN MoMo, Orange Money, Visa, Mastercard?).
- **ABAQWA** — pilot merchant count, current categories supported (retail / hospitality / services?).
- **QUATAFOOD** / **88BASKET** / **88BRICKZ** / **O3MALL** / **QMEDIQ** — projected launch dates if known (currently `coming_soon` or `planned` with TBA).

Currently every "real metric" placeholder reads "TBA" or "Coming soon" — fine pre-launch, but if you want a stat strip on the homepage we need numbers we can publish.

---

## 2. Customer testimonials

Engineering has wired a `testimonials` section component ([components/site/sections/testimonials.tsx](../frontend/components/site/sections/testimonials.tsx)) but no testimonials are seeded — there are none yet.

Per testimonial, we need: quote text, customer name, title, company, optional headshot, and which product they use (so we can show it on the relevant product page).

---

## 3. Partner case studies

For each partner type (Business / Strategic / Investor / Service): 1–3 named partners we can showcase, with permission. Until then, the partner pages have no logo wall — the right call (fake logos are worse than no logos).

---

## 4. Brand assets still missing

| # | Asset | Path | Today |
|---|---|---|---|
| 1 | Founder headshot | [frontend/public/images/about/founder.jpg](../frontend/public/images/about/founder.jpg) | stock |
| 2 | QUATAPAY dashboard screenshot | `frontend/public/images/ecosystem/quatapay/hero.jpg` | gradient |
| 3 | ABAQWA dashboard screenshot | `frontend/public/images/ecosystem/abaqwa/hero.jpg` | gradient |
| 4 | Real 88BASKET logo | `frontend/public/ecosystem/logos/88basket.svg` | placeholder SVG |
| 5 | Real QMEDIQ logo | `frontend/public/ecosystem/logos/qmediq.svg` | placeholder SVG |
| 6 | First-party photography | `frontend/public/images/**` | picsum placeholders |

Drop them in with the same filenames; no code change needed.

---

## 5. Hiring process detail

Currently only **one** real role is seeded (Business Development & Partnerships Manager). For each additional role we open we need:

- Title, department, location, employment type, summary, full description, responsibilities, requirements.
- Salary disclosure policy — published range / "competitive" / "depends on level"?
- Hiring stages (so we can render a 4–6 step diagram).
- Average time-to-hire.
- Benefits & perks summary.

The schema ([Job](../backend/app/models/career.py)) already supports all of this — we just need text.

---

## 6. Press / awards

When the first press mentions or awards land, send: outlet name, headline,
link, date. Engineering will add a `<press-strip>` to the home page (component
already exists at [components/site/sections/press-strip.tsx](../frontend/components/site/sections/press-strip.tsx); empty array today).

---

## 7. Office locations

For about / contact pages: real address(es), phone(s), photo per office. Set
`NEXT_PUBLIC_CONTACT_PHONE` in `frontend/.env.production` to surface the
public phone in the footer + contact page (the row is currently hidden).

---

## 8. Legal & compliance

Items deferred to legal review (also tracked in [BOSS_ACTIONS.md](../BOSS_ACTIONS.md) #8):

- Cameroonian lawyer review of `/privacy` and `/terms` against Loi n° 2010/012.
- Confirmation `privacy@quatadigital.com` and `security@quatadigital.com` are monitored.
- GDPR / NDPR / POPIA posture statement if/when expanding outside Cameroon.
- Regulatory licence references (e.g. CBN payment service provider) if they exist for the launch market.

---

## 9. Newsletter destination

Decision needed (also [BOSS_ACTIONS.md](../BOSS_ACTIONS.md) #9):
- "Keep the in-DB list" — already shipped, admin can export CSV; or
- "Sync to Mailchimp / ConvertKit / Buttondown / Beehiiv" — provide the API key and engineering wires the sync.

---

## 10. Anything we shouldn't say

- Topics with an official position (e.g. crypto, central-bank digital currency).
- Competitors we should never name.
- Active legal/regulatory matters that should not be discussed publicly.

These shape what we can ship in blog posts, the partner FAQ, and the public
contact page reasons dropdown.
