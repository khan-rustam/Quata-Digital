/**
 * Pure server-safe markdown renderer.
 *
 * No React, no client state — just `(string) => HTML string`. Used by the
 * public CMS renderer (Server Components) and re-exported by the admin
 * `MarkdownPreview` client component for parity in the blog editor preview.
 *
 * Handles: headings, bold, italic, inline code, links, images, blockquotes,
 * unordered + ordered lists, horizontal rules, fenced code blocks, paragraphs.
 *
 * Not a full CommonMark implementation — but it covers the editorial
 * subset we need across the admin and public surface.
 */

const escapeHtml = (s: string) =>
  s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");

/**
 * Protocol allow-list for markdown link and image URLs.
 *
 * CMS authors can produce `[text](javascript:alert(1))` or
 * `![x](data:text/html,<script>...)` if we don't filter. We restrict to
 * the protocols a legitimate marketing page actually needs:
 *
 *   - `https:` — external
 *   - `mailto:` and `tel:` — contact links
 *   - root-relative paths (`/something`)
 *   - same-document anchors (`#section`)
 *   - inline images via `data:image/...`
 *
 * Anything else collapses to `#` so the markup is still valid but inert.
 */
function safeUrl(href: string, opts: { allowDataImage?: boolean } = {}): string {
  const trimmed = href.trim();
  if (!trimmed) return "#";
  if (/^https?:/i.test(trimmed)) return trimmed;
  if (/^mailto:/i.test(trimmed)) return trimmed;
  if (/^tel:/i.test(trimmed)) return trimmed;
  if (trimmed.startsWith("/")) return trimmed;
  if (trimmed.startsWith("#")) return trimmed;
  if (opts.allowDataImage && /^data:image\//i.test(trimmed)) return trimmed;
  return "#";
}

function inline(s: string): string {
  let out = escapeHtml(s);
  // images ![alt](url) — must run before links since they share []() syntax.
  out = out.replace(
    /!\[([^\]]*)\]\(([^)\s]+)\)/g,
    (_m, alt, url) => {
      const safe = safeUrl(url, { allowDataImage: true });
      return `<img src="${safe}" alt="${alt}" class="my-3 rounded-xl border border-border max-w-full h-auto" loading="lazy" />`;
    },
  );
  // links [text](url)
  out = out.replace(
    /\[([^\]]+)\]\(([^)\s]+)\)/g,
    (_m, text, url) => {
      const safe = safeUrl(url);
      return `<a href="${safe}" target="_blank" rel="noreferrer noopener" class="text-primary underline-offset-4 hover:underline">${text}</a>`;
    },
  );
  // bold
  out = out.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  // italic
  out = out.replace(/(^|\W)\*([^*]+)\*(?=\W|$)/g, "$1<em>$2</em>");
  out = out.replace(/(^|\W)_([^_]+)_(?=\W|$)/g, "$1<em>$2</em>");
  // inline code
  out = out.replace(
    /`([^`]+)`/g,
    '<code class="rounded bg-secondary px-1 py-0.5 text-[12px] font-mono">$1</code>',
  );
  return out;
}

export function renderMarkdownToHtml(md: string): string {
  const lines = md.replace(/\r\n/g, "\n").split("\n");
  const out: string[] = [];
  let i = 0;
  let inUl = false;
  let inOl = false;
  let inPara: string[] = [];

  function closePara() {
    if (inPara.length) {
      out.push(`<p class="my-3 leading-relaxed">${inline(inPara.join(" "))}</p>`);
      inPara = [];
    }
  }
  function closeLists() {
    if (inUl) { out.push("</ul>"); inUl = false; }
    if (inOl) { out.push("</ol>"); inOl = false; }
  }

  while (i < lines.length) {
    const line = lines[i];
    if (/^```/.test(line)) {
      closePara();
      closeLists();
      const lang = line.slice(3).trim();
      const code: string[] = [];
      i++;
      while (i < lines.length && !/^```/.test(lines[i])) {
        code.push(lines[i]);
        i++;
      }
      i++;
      out.push(
        `<pre class="my-4 overflow-x-auto rounded-xl border border-border bg-surface-soft p-4 text-xs font-mono"><code data-lang="${escapeHtml(lang)}">${escapeHtml(code.join("\n"))}</code></pre>`,
      );
      continue;
    }
    const h = /^(#{1,6})\s+(.+)$/.exec(line);
    if (h) {
      closePara();
      closeLists();
      const level = h[1].length;
      const sizes: Record<number, string> = {
        1: "mt-6 mb-3 text-3xl font-semibold tracking-tight",
        2: "mt-6 mb-2 text-2xl font-semibold tracking-tight",
        3: "mt-5 mb-2 text-xl font-semibold tracking-tight",
        4: "mt-4 mb-2 text-lg font-semibold",
        5: "mt-4 mb-1 text-base font-semibold",
        6: "mt-3 mb-1 text-sm font-semibold uppercase tracking-wider text-muted-foreground",
      };
      out.push(`<h${level} class="${sizes[level]}">${inline(h[2])}</h${level}>`);
      i++;
      continue;
    }
    if (/^---+\s*$/.test(line)) {
      closePara();
      closeLists();
      out.push('<hr class="my-6 border-border" />');
      i++;
      continue;
    }
    if (/^>\s?/.test(line)) {
      closePara();
      closeLists();
      const quote: string[] = [];
      while (i < lines.length && /^>\s?/.test(lines[i])) {
        quote.push(lines[i].replace(/^>\s?/, ""));
        i++;
      }
      out.push(
        `<blockquote class="my-4 border-l-2 border-primary/40 bg-surface-soft pl-4 py-2 text-foreground/80">${inline(quote.join(" "))}</blockquote>`,
      );
      continue;
    }
    const ul = /^[-*]\s+(.*)$/.exec(line);
    if (ul) {
      closePara();
      if (inOl) { out.push("</ol>"); inOl = false; }
      if (!inUl) { out.push('<ul class="my-3 ml-5 list-disc space-y-1">'); inUl = true; }
      out.push(`<li>${inline(ul[1])}</li>`);
      i++;
      continue;
    }
    const ol = /^\d+\.\s+(.*)$/.exec(line);
    if (ol) {
      closePara();
      if (inUl) { out.push("</ul>"); inUl = false; }
      if (!inOl) { out.push('<ol class="my-3 ml-5 list-decimal space-y-1">'); inOl = true; }
      out.push(`<li>${inline(ol[1])}</li>`);
      i++;
      continue;
    }
    if (!line.trim()) {
      closePara();
      closeLists();
      i++;
      continue;
    }
    inPara.push(line);
    i++;
  }
  closePara();
  closeLists();
  return out.join("\n");
}
