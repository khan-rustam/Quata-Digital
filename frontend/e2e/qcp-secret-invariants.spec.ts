import { readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";
import { expect, test } from "@playwright/test";

/**
 * Static guards over the QCP admin console.
 *
 * The QCP console is the only admin surface that handles live Meta
 * credentials and product API keys. Its central promise is that **no stored
 * secret is ever rendered** — not a token, not an app secret, not an API key,
 * not a prefix of one. The backend already refuses to return them; these
 * tests stop the frontend from acquiring a way to display one anyway.
 *
 * They are deliberately source-level rather than browser-level. The property
 * being protected is "this code cannot show a secret", which is a property of
 * the source, and checking it statically means it holds for every state of
 * every screen rather than only the ones a fixture happened to reach. They
 * need no server and no browser.
 *
 * The one legitimate exception is a freshly minted product key, which is
 * shown exactly once at mint. It is confined to `MintedKeyDialog` in
 * `products/page.tsx`, and the third test pins that confinement.
 */

const QCP_DIR = path.resolve(__dirname, "../app/admin/qcp");

/** Credential-bearing field names. Mirrors `SECRET_FIELDS` in qcp/api.ts. */
const SECRET_NAMES = [
  "access_token",
  "app_secret",
  "webhook_verify_token",
  "verify_token",
  "webhook_secret",
  "api_key_hash",
];

function sources(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = path.join(dir, entry);
    if (statSync(full).isDirectory()) out.push(...sources(full));
    else if (/\.tsx?$/.test(entry)) out.push(full);
  }
  return out;
}

function rel(file: string) {
  return path.relative(path.resolve(__dirname, ".."), file);
}

/**
 * Lines that actually execute, as `[1-indexed line number, text]`.
 *
 * Comments are excluded: these files document *why* a secret is not rendered,
 * so the prose necessarily names the things the code must not do. A comment
 * cannot put a token on screen; only code can.
 */
function codeLines(text: string): [number, string][] {
  const out: [number, string][] = [];
  let inBlock = false;
  text.split("\n").forEach((line, i) => {
    const trimmed = line.trim();
    if (inBlock) {
      if (trimmed.includes("*/")) inBlock = false;
      return;
    }
    if (trimmed.startsWith("/*")) {
      if (!trimmed.includes("*/")) inBlock = true;
      return;
    }
    if (trimmed.startsWith("//") || trimmed.startsWith("*")) return;
    out.push([i + 1, line]);
  });
  return out;
}

test.describe("QCP console — secret handling", () => {
  test("no credential field is ever prefilled from API data", () => {
    // A `value=` or `defaultValue=` that mentions a credential name is the
    // one mistake that would put a live token on screen: it means somebody
    // believed the API hands the value back, and one day a backend build
    // will. Credential inputs are write-only and must stay that way.
    const offenders: string[] = [];

    for (const file of sources(QCP_DIR)) {
      for (const [no, line] of codeLines(readFileSync(file, "utf8"))) {
        const prefill = /(?:^|\s)(?:default)?[Vv]alue\s*=\s*\{([^}]*)\}/g;
        let m: RegExpExecArray | null;
        while ((m = prefill.exec(line)) !== null) {
          const expr = m[1];
          for (const name of SECRET_NAMES) {
            if (expr.includes(name)) {
              offenders.push(`${rel(file)}:${no} → ${line.trim()}`);
            }
          }
        }
      }
    }

    expect(
      offenders,
      `A QCP input is prefilled from a credential field. Credential inputs are write-only: they show presence, never a value.\n${offenders.join("\n")}`
    ).toEqual([]);
  });

  test("no QCP screen persists anything to browser storage", () => {
    // A minted API key lives in React state for one dialog and then is gone.
    // Persisting any QCP state to localStorage/sessionStorage/cookies would
    // outlive that dialog and survive a reload, which is precisely the
    // property "shown once" is supposed to deny.
    const offenders: string[] = [];

    for (const file of sources(QCP_DIR)) {
      for (const [no, line] of codeLines(readFileSync(file, "utf8"))) {
        if (/\b(localStorage|sessionStorage|document\.cookie)\b/.test(line)) {
          offenders.push(`${rel(file)}:${no} → ${line.trim()}`);
        }
      }
    }

    expect(
      offenders,
      `A QCP screen writes to browser storage. Nothing here may outlive its dialog.\n${offenders.join("\n")}`
    ).toEqual([]);
  });

  test("the plaintext API key is confined to the mint dialog", () => {
    // `api_key` (as opposed to `api_key_prefix` / `has_api_key`) is the
    // plaintext. It is allowed in exactly two files: api.ts, which types the
    // mint response, and products/page.tsx, which renders it once.
    const allowed = new Set(["app/admin/qcp/api.ts", "app/admin/qcp/products/page.tsx"]);
    const offenders: string[] = [];

    for (const file of sources(QCP_DIR)) {
      const relative = rel(file);
      if (allowed.has(relative)) continue;
      for (const [no, line] of codeLines(readFileSync(file, "utf8"))) {
        // `api_key_prefix` and `has_api_key` are safe; bare `api_key` is not.
        if (/\bapi_key\b(?!_prefix)/.test(line) && !/has_api_key/.test(line)) {
          offenders.push(`${relative}:${no} → ${line.trim()}`);
        }
      }
    }

    expect(
      offenders,
      `A plaintext product key escaped the mint dialog.\n${offenders.join("\n")}`
    ).toEqual([]);
  });

  test("every credential the account shape carries is on the strip list", () => {
    // `stripSecrets` is the last line of defence on the write path. If the
    // account shape grows a credential, it has to be added there too — this
    // fails the build when the two drift apart.
    const api = readFileSync(path.join(QCP_DIR, "api.ts"), "utf8");
    const listed = api
      .slice(api.indexOf("export const SECRET_FIELDS"), api.indexOf("] as const", api.indexOf("export const SECRET_FIELDS")));

    for (const name of SECRET_NAMES) {
      expect(listed, `${name} is not in SECRET_FIELDS`).toContain(`"${name}"`);
    }
  });
});
