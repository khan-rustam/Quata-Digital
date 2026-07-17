import fs from "node:fs";
import path from "node:path";
import { ImageResponse } from "next/og";

/**
 * Shared OG image template so every marketing route uses the same brand
 * language. Each route picks an `eyebrow`, a `title` and a short `tagline`,
 * plus a footer URL slug — the rest of the visual treatment stays consistent.
 *
 * Two variants:
 *   light — the default; matches the site's white chrome.
 *   dark  — for content cards (blog posts, job posts, the homepage) that
 *           benefit from standing out in a social feed.
 *
 * Both variants show the real full-colour lockup: the artwork's teal reads on
 * white and its gold reads on ink, so no knockout variant is needed. That does
 * mean the dark ramp must stay dark — see BACKGROUND below.
 */

export const OG_SIZE = { width: 1200, height: 630 } as const;
export const OG_CONTENT_TYPE = "image/png" as const;

const LOCKUP_W = 320;
const LOCKUP_H = 83; // public/brand/lockup.png is 1200x310 — keep this ratio.

/**
 * Artwork inlined as data URIs.
 *
 * Satori cannot resolve the site's own URLs, so OG artwork has to be embedded
 * rather than linked. Read from `public/` and not `brand/`: the runtime image
 * only copies `public/` (see Dockerfile), so the masters aren't there. Cached
 * because the homepage card is ISR and re-renders on a 60s revalidate.
 */
const dataUriCache = new Map<string, string>();

function dataUri(relPath: string, mime: string): string {
  let cached = dataUriCache.get(relPath);
  if (cached === undefined) {
    const file = path.join(process.cwd(), "public", relPath);
    cached = `data:${mime};base64,${fs.readFileSync(file).toString("base64")}`;
    dataUriCache.set(relPath, cached);
  }
  return cached;
}

const lockupSrc = () => dataUri("brand/lockup.png", "image/png");

/**
 * Background artwork, generated into `public/brand/og/` from `brand/og/`.
 * Each is a background *only* — no logo and no text is baked in, because
 * image models mangle both. The real lockup and real type are drawn over the
 * top here, which is the whole point of compositing rather than shipping a
 * finished AI card. Picking a background implies the dark variant.
 */
type OgBackground = "home" | "blog" | "careers";

const backgroundSrc = (key: OgBackground) => dataUri(`brand/og/${key}.jpg`, "image/jpeg");

/**
 * Darkening scrim laid over the background art.
 *
 * The abstract cards are already near-black on the left, so this barely
 * touches them. It exists for `careers`, which is a photograph: its left zone
 * is a window-lit wall bright enough that white text measured 1.77:1 against
 * it — unreadable. Fading left-to-right keeps the subjects on the right
 * visible while making the text column safe.
 */
const SCRIM =
  "linear-gradient(90deg, rgba(8,12,16,0.94) 0%, rgba(8,12,16,0.82) 42%, rgba(8,12,16,0.42) 74%, rgba(8,12,16,0.14) 100%)";

/**
 * BACKGROUND: white body text sits on these, so every stop has to clear 4.5:1
 * against white. The dark ramp tops out at #005468 (8.51:1) and deliberately
 * stops short of the logo's bright #0090a8 (3.78:1), which would leave the
 * footer text unreadable in the bottom-right corner where a 135deg gradient
 * is lightest.
 */
const VARIANTS = {
  light: {
    background: "#FAFAF7",
    eyebrow: "#5B6470",
    title: "linear-gradient(135deg,#003048,#0090a8)",
    body: "#0F1216",
    footer: "#5B6470",
    rule: "1px solid #E7E7E2",
  },
  dark: {
    background: "linear-gradient(135deg, #0f1216 0%, #003048 55%, #005468 100%)",
    eyebrow: "#00d8f0",
    title: "none",
    body: "#FFFFFF",
    footer: "rgba(255,255,255,0.75)",
    rule: "1px solid rgba(255,255,255,0.14)",
  },
} as const;

type OgInput = {
  eyebrow?: string;
  title: string;
  tagline?: string;
  /** Renders bottom-left as `quatadigital.com{pathname}` unless `footerLeft` overrides it. */
  pathname: string;
  footerLeft?: string;
  footerRight?: string;
  variant?: keyof typeof VARIANTS;
  /** Background artwork key. Implies `variant: "dark"`. */
  background?: OgBackground;
};

export function renderOg({
  eyebrow,
  title,
  tagline,
  pathname,
  footerLeft,
  footerRight = "One ecosystem · Many doorways",
  variant = "light",
  background,
}: OgInput) {
  // Background art is always dark, so it forces the dark type ramp regardless
  // of what the caller passed — light type on these would be invisible.
  const resolved = background ? "dark" : variant;
  const v = VARIANTS[resolved];

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          position: "relative",
          background: v.background,
          color: v.body,
          display: "flex",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        {background ? (
          <>
            {/* eslint-disable-next-line @next/next/no-img-element -- satori renders raw <img>; next/image is not available inside ImageResponse. */}
            <img
              src={backgroundSrc(background)}
              width={OG_SIZE.width}
              height={OG_SIZE.height}
              alt=""
              style={{ position: "absolute", top: 0, left: 0 }}
            />
            <div
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                width: OG_SIZE.width,
                height: OG_SIZE.height,
                background: SCRIM,
                display: "flex",
              }}
            />
          </>
        ) : null}

        <div
          style={{
            position: "relative",
            width: "100%",
            height: "100%",
            padding: "80px",
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
          }}
        >
        <div style={{ display: "flex" }}>
          {/* eslint-disable-next-line @next/next/no-img-element -- satori renders raw <img>; next/image is not available inside ImageResponse. */}
          <img src={lockupSrc()} width={LOCKUP_W} height={LOCKUP_H} alt="QUATA Digital" />
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          {eyebrow ? (
            <div
              style={{
                display: "flex",
                fontSize: 24,
                color: v.eyebrow,
                textTransform: "uppercase",
                letterSpacing: 4,
                fontWeight: 600,
              }}
            >
              {eyebrow}
            </div>
          ) : null}
          <div
            style={{
              display: "flex",
              fontSize: 84,
              fontWeight: 700,
              letterSpacing: -3,
              lineHeight: 1.04,
              maxWidth: 980,
              ...(resolved === "light"
                ? { background: v.title, backgroundClip: "text", color: "transparent" }
                : { color: v.body }),
            }}
          >
            {title}
          </div>
          {tagline ? (
            <div
              style={{
                display: "flex",
                fontSize: 32,
                color: resolved === "dark" ? "rgba(255,255,255,0.78)" : v.body,
                maxWidth: 980,
                lineHeight: 1.25,
              }}
            >
              {tagline}
            </div>
          ) : null}
        </div>

        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            color: v.footer,
            fontSize: 22,
            borderTop: v.rule,
            paddingTop: 24,
          }}
        >
          <div style={{ display: "flex" }}>
            {footerLeft ?? `quatadigital.com${pathname}`}
          </div>
          <div style={{ display: "flex" }}>{footerRight}</div>
        </div>
        </div>
      </div>
    ),
    { ...OG_SIZE }
  );
}
