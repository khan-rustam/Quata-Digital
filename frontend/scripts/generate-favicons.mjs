import sharp from "sharp";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(__dirname, "..");
const APP_DIR = path.join(FRONTEND, "app");
const PUBLIC_DIR = path.join(FRONTEND, "public");
const SOURCE = path.join(PUBLIC_DIR, "logo.png");

const BRAND_BG = { r: 255, g: 255, b: 255, alpha: 1 };
const MASKABLE_BG = { r: 11, g: 31, b: 27, alpha: 1 };

async function cropToIconSquare(srcBuffer) {
  const img = sharp(srcBuffer).ensureAlpha();
  const meta = await img.metadata();
  const w = meta.width ?? 0;
  const h = meta.height ?? 0;
  if (!w || !h) throw new Error("logo.png has no dimensions");

  // The hexagon icon occupies roughly the leftmost ~46% of the logo;
  // the rest is the "QUATA DIGITAL" wordmark. Crop only the icon and
  // centre it on a transparent square so favicons stay legible.
  const iconWidth = Math.round(w * 0.46);
  const iconHeight = h;
  const left = 0;
  const top = 0;

  const iconBuffer = await sharp(srcBuffer)
    .ensureAlpha()
    .extract({ left, top, width: iconWidth, height: iconHeight })
    .toBuffer();

  const side = Math.max(iconWidth, iconHeight);
  return sharp({
    create: {
      width: side,
      height: side,
      channels: 4,
      background: { r: 0, g: 0, b: 0, alpha: 0 },
    },
  })
    .composite([
      {
        input: iconBuffer,
        left: Math.round((side - iconWidth) / 2),
        top: Math.round((side - iconHeight) / 2),
      },
    ])
    .png()
    .toBuffer();
}

async function makePng(squareBuffer, size, opts = {}) {
  const { background = BRAND_BG, padding = 0.08, rounded = false } = opts;
  const innerSize = Math.round(size * (1 - padding * 2));
  const offset = Math.round((size - innerSize) / 2);

  const resized = await sharp(squareBuffer)
    .resize(innerSize, innerSize, { fit: "contain", background: { r: 0, g: 0, b: 0, alpha: 0 } })
    .toBuffer();

  let pipeline = sharp({
    create: {
      width: size,
      height: size,
      channels: 4,
      background,
    },
  }).composite([{ input: resized, left: offset, top: offset }]);

  if (rounded) {
    const r = Math.round(size * 0.22);
    const mask = Buffer.from(
      `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}"><rect width="${size}" height="${size}" rx="${r}" ry="${r}" fill="#fff"/></svg>`
    );
    pipeline = pipeline.composite([
      { input: resized, left: offset, top: offset },
      { input: mask, blend: "dest-in" },
    ]);
  }

  return pipeline.png({ compressionLevel: 9 }).toBuffer();
}

function buildIco(pngs) {
  const ICONDIR = Buffer.alloc(6);
  ICONDIR.writeUInt16LE(0, 0);
  ICONDIR.writeUInt16LE(1, 2);
  ICONDIR.writeUInt16LE(pngs.length, 4);

  const ENTRY_SIZE = 16;
  const HEADER_SIZE = 6 + ENTRY_SIZE * pngs.length;

  const entries = [];
  const datas = [];
  let offset = HEADER_SIZE;

  for (const { size, data } of pngs) {
    const entry = Buffer.alloc(ENTRY_SIZE);
    entry.writeUInt8(size >= 256 ? 0 : size, 0);
    entry.writeUInt8(size >= 256 ? 0 : size, 1);
    entry.writeUInt8(0, 2);
    entry.writeUInt8(0, 3);
    entry.writeUInt16LE(1, 4);
    entry.writeUInt16LE(32, 6);
    entry.writeUInt32LE(data.length, 8);
    entry.writeUInt32LE(offset, 12);
    entries.push(entry);
    datas.push(data);
    offset += data.length;
  }

  return Buffer.concat([ICONDIR, ...entries, ...datas]);
}

async function main() {
  const src = await fs.readFile(SOURCE);
  const square = await cropToIconSquare(src);

  // Standard sizes used across browsers, PWAs, OG, and search results.
  const targets = [
    { name: "icon.png", size: 32, dest: APP_DIR },
    { name: "icon1.png", size: 192, dest: APP_DIR },
    { name: "icon2.png", size: 512, dest: APP_DIR },
    { name: "apple-icon.png", size: 180, dest: APP_DIR, rounded: false },
    { name: "icon-maskable-192.png", size: 192, dest: PUBLIC_DIR, background: MASKABLE_BG, padding: 0.18 },
    { name: "icon-maskable-512.png", size: 512, dest: PUBLIC_DIR, background: MASKABLE_BG, padding: 0.18 },
  ];

  for (const t of targets) {
    const buf = await makePng(square, t.size, {
      background: t.background ?? BRAND_BG,
      padding: t.padding ?? 0.08,
      rounded: t.rounded ?? false,
    });
    const out = path.join(t.dest, t.name);
    await fs.writeFile(out, buf);
    console.log("wrote", path.relative(FRONTEND, out), `(${t.size}x${t.size})`);
  }

  const icoSizes = [16, 32, 48];
  const icoPngs = await Promise.all(
    icoSizes.map(async (size) => ({
      size,
      data: await makePng(square, size, { padding: 0.06 }),
    }))
  );
  const ico = buildIco(icoPngs);
  const icoPath = path.join(APP_DIR, "favicon.ico");
  await fs.writeFile(icoPath, ico);
  console.log("wrote", path.relative(FRONTEND, icoPath), `(${icoSizes.join("+")})`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
