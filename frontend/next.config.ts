import type { NextConfig } from "next";

/**
 * Security baseline.
 *
 * CSP is shipped in **Report-Only** mode for the first month after launch
 * so violations surface in browser devtools and (optionally) a reporting
 * endpoint without breaking the page. Promote `Content-Security-Policy-Report-Only`
 * to `Content-Security-Policy` once the report stream is clean.
 */
const cspReportOnly = [
  "default-src 'self'",
  // Next dev needs 'unsafe-eval'; in production we only need 'unsafe-inline'
  // for the framer-motion inline styles + Next.js inline boot script. The
  // 'self' covers /_next/static/* chunks.
  "script-src 'self' 'unsafe-inline' https://hcaptcha.com https://*.hcaptcha.com",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob: https:",
  "font-src 'self' data:",
  // Backend API + WebSocket. Falls back to localhost in dev.
  "connect-src 'self' https://*.quatadigital.com wss://*.quatadigital.com http://localhost:8000 ws://localhost:8000 https://hcaptcha.com https://*.hcaptcha.com",
  "frame-src https://hcaptcha.com https://*.hcaptcha.com",
  "frame-ancestors 'none'",
  "form-action 'self'",
  "base-uri 'self'",
  "object-src 'none'",
  "upgrade-insecure-requests",
].join("; ");

// Env-driven toggles (string env vars on Vercel / process.env in Node).
// `CSP_ENFORCE=true` swaps Report-Only for the real enforce header.
// `HSTS_PRELOAD=true` adds the `preload` directive — only flip ON after
// the apex passes https://hstspreload.org/.
const cspEnforce = (process.env.CSP_ENFORCE ?? "").toLowerCase() === "true";
const hstsPreload = (process.env.HSTS_PRELOAD ?? "").toLowerCase() === "true";

const hstsValue = `max-age=63072000; includeSubDomains${hstsPreload ? "; preload" : ""}`;

const securityHeaders = [
  // Force HTTPS for two years and apply to subdomains. `; preload` is
  // controlled by HSTS_PRELOAD — don't enable until the domain has been
  // verified on https://hstspreload.org/.
  { key: "Strict-Transport-Security", value: hstsValue },
  // Block clickjacking attempts on the admin shell.
  { key: "X-Frame-Options", value: "DENY" },
  // Prevent MIME-type sniffing attacks.
  { key: "X-Content-Type-Options", value: "nosniff" },
  // Send only the origin on cross-origin navigations — no full URL leaks.
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  // Lock down powerful browser APIs we never use.
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
  },
  // Cross-origin protections.
  { key: "X-DNS-Prefetch-Control", value: "on" },
  // CSP — defaults to Report-Only so violations surface in devtools without
  // breaking the page. Flip CSP_ENFORCE=true after a clean reporting window.
  {
    key: cspEnforce ? "Content-Security-Policy" : "Content-Security-Policy-Report-Only",
    value: cspReportOnly,
  },
];

const nextConfig: NextConfig = {
  // Don't advertise the framework.
  poweredByHeader: false,

  // `standalone` build emits .next/standalone/ — a minimal Node bundle
  // that the runtime image copies without dragging in full
  // `node_modules`. Cuts the production image from ~1 GB to ~250 MB.
  output: "standalone",

  // Whitelist of hosts allowed to be loaded through next/image. CMS
  // authors can paste these into Hero / image_text sections; anything
  // else fails at build/runtime instead of silently bypassing the
  // image optimiser.
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "quatadigital.com" },
      { protocol: "https", hostname: "*.quatadigital.com" },
      { protocol: "https", hostname: "*.s3.amazonaws.com" },
      { protocol: "https", hostname: "*.r2.cloudflarestorage.com" },
      { protocol: "https", hostname: "*.backblazeb2.com" },
    ],
  },

  async headers() {
    return [
      {
        source: "/:path*",
        headers: securityHeaders,
      },
    ];
  },
};

export default nextConfig;
