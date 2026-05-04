import type { NextConfig } from "next";

/**
 * Security baseline.
 *
 * No CSP yet — script-src needs per-environment tuning (next/script, framer
 * inline styles, etc.). Add it in a follow-up after measuring violations
 * against `Content-Security-Policy-Report-Only` first.
 */
const securityHeaders = [
  // Force HTTPS for two years and apply to subdomains. Don't add `preload`
  // until the apex domain is verified on https://hstspreload.org/.
  { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" },
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
];

const nextConfig: NextConfig = {
  // Don't advertise the framework.
  poweredByHeader: false,

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
