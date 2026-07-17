/**
 * Brand asset pipeline.
 *
 * Masters live in `frontend/brand/` — they are git-tracked but NOT inside
 * `public/`, so the multi-megabyte originals are never served to a browser.
 * Everything a browser actually downloads is generated from them by this
 * script:
 *
 *   brand/mark.png            -> app/favicon.ico, app/icon*.png, app/apple-icon.png,
 *                                public/icon-maskable-*.png
 *   brand/header-lockup.png   -> public/brand/lockup.png  (navbar + footer + OG)
 *   brand/og/*.png            -> public/brand/og/*.jpg    (OG card backgrounds)
 *
 * `brand/social/` holds artwork for decks, ads and social posts. Nothing on the
 * site renders it, so it has no derivative here and is never served.
 *
 * Run after any change to the masters:  node scripts/generate-favicons.mjs
 *
 * The masters carry a lot of transparent margin (header-lockup.png is
 * 6000x3375 with only 4766x1232 of actual artwork). We trim that margin
 * first, otherwise every downstream asset renders the logo tiny inside a
 * mostly-empty box, and the padding added below would stack on top of
 * padding that is already baked in.
 */
import sharp from "sharp";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(__dirname, "..");
const APP_DIR = path.join(FRONTEND, "app");
const PUBLIC_DIR = path.join(FRONTEND, "public");
const BRAND_SRC = path.join(FRONTEND, "brand");
const BRAND_OUT = path.join(PUBLIC_DIR, "brand");

const MARK = path.join(BRAND_SRC, "mark.png");
const HEADER_LOCKUP = path.join(BRAND_SRC, "header-lockup.png");
// `brand/stacked-lockup.png` is also a master, but nothing renders a square
// lockup today so no derivative is emitted for it. See the note in main().

const OG_SIZE = { width: 1200, height: 630 };

/** OG card backgrounds. Keys match the `background` values in lib/og-template.tsx. */
const OG_BACKGROUNDS = ["home", "blog", "careers"];

const TRANSPARENT = { r: 0, g: 0, b: 0, alpha: 0 };
const WHITE = { r: 255, g: 255, b: 255, alpha: 1 };

/** Strip the transparent margin baked into the master artwork. */
async function trimmed(file) {
  return sharp(file).ensureAlpha().trim({ threshold: 1 }).png().toBuffer();
}

/**
 * Centre artwork of any aspect ratio on a transparent square canvas.
 * The QD mark is 716x535 once trimmed — letterboxing it keeps the circles
 * round instead of stretching them to fill a square icon slot.
 */
async function squareCanvas(buffer) {
  const { width, height } = await sharp(buffer).metadata();
  const side = Math.max(width, height);
  return sharp({
    create: { width: side, height: side, channels: 4, background: TRANSPARENT },
  })
    .composite([
      {
        input: buffer,
        left: Math.round((side - width) / 2),
        top: Math.round((side - height) / 2),
      },
    ])
    .png()
    .toBuffer();
}

/** Render a square master down to `size`, on `background`, with `padding` breathing room. */
async function icon(squareBuffer, size, { background = TRANSPARENT, padding = 0.08 } = {}) {
  const inner = Math.round(size * (1 - padding * 2));
  const offset = Math.round((size - inner) / 2);
  const resized = await sharp(squareBuffer)
    .resize(inner, inner, { fit: "contain", background: TRANSPARENT })
    .toBuffer();

  return sharp({ create: { width: size, height: size, channels: 4, background } })
    .composite([{ input: resized, left: offset, top: offset }])
    .png({ compressionLevel: 9 })
    .toBuffer();
}

/**
 * Resize a lockup to a fixed width, preserving aspect ratio.
 *
 * Full RGBA rather than a 256-colour palette: palette quantisation cuts these
 * to ~1/5th the size but dithers visible speckle through the mark's metallic
 * gradients. `next/image` re-encodes to WebP/AVIF at the actual display size,
 * so what a browser downloads is a fraction of this either way — the source
 * only needs to stay clean.
 */
async function lockup(buffer, width) {
  return sharp(buffer)
    .resize({ width, fit: "inside", withoutEnlargement: true })
    .png({ compressionLevel: 9 })
    .toBuffer();
}

/**
 * Render an OG card background to exactly 1200x630.
 *
 * JPEG, not PNG: these are photographic gradients with no transparency, so
 * PNG costs ~13x the bytes for no gain (882 KB vs 65 KB on the home card).
 * Not WebP — satori, which renders the OG cards, cannot decode it.
 *
 * The generated art is already ~1.90:1, so `cover` trims a few pixels rather
 * than recomposing; the deliberate empty zone on the left survives intact.
 */
async function ogBackground(file) {
  return sharp(file)
    .resize(OG_SIZE.width, OG_SIZE.height, { fit: "cover" })
    .jpeg({ quality: 90, mozjpeg: true })
    .toBuffer();
}

/**
 * Pack PNGs into a multi-resolution .ico.
 *
 * PNG-compressed ICO entries are read by every browser we support and keep
 * the file far smaller than the equivalent BMP payload.
 */
function buildIco(pngs) {
  const ENTRY_SIZE = 16;
  const header = Buffer.alloc(6);
  header.writeUInt16LE(0, 0); // reserved
  header.writeUInt16LE(1, 2); // type: icon
  header.writeUInt16LE(pngs.length, 4);

  const entries = [];
  const datas = [];
  let offset = 6 + ENTRY_SIZE * pngs.length;

  for (const { size, data } of pngs) {
    const entry = Buffer.alloc(ENTRY_SIZE);
    entry.writeUInt8(size >= 256 ? 0 : size, 0); // width  (0 means 256)
    entry.writeUInt8(size >= 256 ? 0 : size, 1); // height (0 means 256)
    entry.writeUInt8(0, 2); // palette size
    entry.writeUInt8(0, 3); // reserved
    entry.writeUInt16LE(1, 4); // colour planes
    entry.writeUInt16LE(32, 6); // bits per pixel
    entry.writeUInt32LE(data.length, 8);
    entry.writeUInt32LE(offset, 12);
    entries.push(entry);
    datas.push(data);
    offset += data.length;
  }

  return Buffer.concat([header, ...entries, ...datas]);
}

async function write(dir, name, buffer, note) {
  const out = path.join(dir, name);
  await fs.writeFile(out, buffer);
  const kb = (buffer.length / 1024).toFixed(1);
  console.log(`  ${path.relative(FRONTEND, out).padEnd(36)} ${String(kb).padStart(7)} KB  ${note}`);
}

async function main() {
  await fs.mkdir(BRAND_OUT, { recursive: true });

  const markSquare = await squareCanvas(await trimmed(MARK));

  console.log("\nApp icons (Next.js file conventions — auto-linked into <head>)");

  // Transparent so the mark sits on the browser's own tab colour rather than
  // a white card that would glow on dark themes.
  await write(APP_DIR, "icon.png", await icon(markSquare, 32), "browser tab");
  await write(APP_DIR, "icon1.png", await icon(markSquare, 192), "PWA / Android");
  await write(APP_DIR, "icon2.png", await icon(markSquare, 512), "PWA / splash");

  // iOS composites Apple touch icons onto black and applies its own squircle
  // mask, so this one must be opaque and must NOT be pre-rounded.
  await write(
    APP_DIR,
    "apple-icon.png",
    await icon(markSquare, 180, { background: WHITE, padding: 0.1 }),
    "iOS home screen (opaque)"
  );

  const icoSizes = [16, 32, 48];
  const icoPngs = await Promise.all(
    icoSizes.map(async (size) => ({ size, data: await icon(markSquare, size, { padding: 0.06 }) }))
  );
  await write(APP_DIR, "favicon.ico", buildIco(icoPngs), `legacy (${icoSizes.join("+")})`);

  console.log("\nMaskable icons (Android crops these to a circle/squircle)");

  // 18% padding keeps the mark inside the maskable safe zone (the centre 80%
  // circle) whatever shape the launcher crops to. White rather than brand
  // teal: half the mark IS teal and would vanish into a teal plate.
  for (const size of [192, 512]) {
    await write(
      PUBLIC_DIR,
      `icon-maskable-${size}.png`,
      await icon(markSquare, size, { background: WHITE, padding: 0.18 }),
      "safe-zone padded"
    );
  }

  console.log("\nWeb lockups (served to browsers)");

  // The navbar renders the lockup at 48-80px tall and the footer at 80px; at
  // 3x DPR that is ~240px of artwork, i.e. ~930px wide. 1200px leaves headroom
  // without shipping the 4.2 MB master.
  //
  // Only the horizontal lockup is emitted, because it is the only one anything
  // renders (navbar, footer, and both OG variants). `brand/stacked-lockup.png`
  // is kept as a master for a future square/portrait slot — add a line here
  // when something actually needs it rather than shipping it unused.
  await write(
    BRAND_OUT,
    "lockup.png",
    await lockup(await trimmed(HEADER_LOCKUP), 1200),
    "navbar + footer + OG"
  );

  console.log("\nOG card backgrounds (composited under the real lockup by lib/og-template.tsx)");

  const ogOut = path.join(BRAND_OUT, "og");
  await fs.mkdir(ogOut, { recursive: true });
  for (const name of OG_BACKGROUNDS) {
    await write(
      ogOut,
      `${name}.jpg`,
      await ogBackground(path.join(BRAND_SRC, "og", `${name}.png`)),
      `${OG_SIZE.width}x${OG_SIZE.height}`
    );
  }

  console.log("");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
