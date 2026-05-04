"use client";

import { useEffect } from "react";

/**
 * Last-resort error boundary. Catches errors thrown in the root layout
 * itself — at which point the regular `app/error.tsx` boundary, the global
 * styles, the navbar, the toast provider — none of it has mounted yet.
 *
 * Keep this file dependency-free on purpose. No design tokens, no shared
 * components, no fonts. Inline styles only.
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[QUATA root error boundary]", error);
  }, [error]);

  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          minHeight: "100vh",
          background: "#FAFAF7",
          color: "#0F1216",
          fontFamily:
            "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "32px",
        }}
      >
        <div style={{ maxWidth: 520, textAlign: "center" }}>
          <div
            style={{
              display: "inline-block",
              padding: "6px 12px",
              borderRadius: 999,
              background: "#FEE2E2",
              color: "#9F1239",
              fontSize: 12,
              fontWeight: 600,
              letterSpacing: 1,
              textTransform: "uppercase",
            }}
          >
            Something broke
          </div>
          <h1
            style={{
              marginTop: 24,
              fontSize: 36,
              lineHeight: 1.15,
              letterSpacing: -1,
              fontWeight: 600,
            }}
          >
            We hit an error loading this page.
          </h1>
          <p
            style={{
              marginTop: 16,
              color: "#5B6470",
              lineHeight: 1.55,
              fontSize: 16,
            }}
          >
            The QUATA team has been notified. You can try reloading, or head
            back to the homepage and try again.
          </p>
          {error?.digest && (
            <code
              style={{
                display: "inline-block",
                marginTop: 16,
                padding: "4px 10px",
                borderRadius: 6,
                background: "#E7E7E2",
                fontSize: 12,
                fontFamily:
                  "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
              }}
            >
              ref: {error.digest}
            </code>
          )}
          <div
            style={{
              marginTop: 32,
              display: "flex",
              justifyContent: "center",
              gap: 8,
              flexWrap: "wrap",
            }}
          >
            <button
              type="button"
              onClick={() => reset()}
              style={{
                padding: "10px 18px",
                borderRadius: 999,
                background: "#0E5B4A",
                color: "white",
                border: "none",
                fontSize: 14,
                fontWeight: 500,
                cursor: "pointer",
              }}
            >
              Try again
            </button>
            {/* eslint-disable-next-line @next/next/no-html-link-for-pages -- global-error sits outside RootLayout, so next/link cannot be used here. */}
            <a
              href="/"
              style={{
                padding: "10px 18px",
                borderRadius: 999,
                border: "1px solid #E7E7E2",
                background: "white",
                color: "#0F1216",
                fontSize: 14,
                fontWeight: 500,
                textDecoration: "none",
              }}
            >
              Back home
            </a>
          </div>
        </div>
      </body>
    </html>
  );
}
