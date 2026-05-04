import { ImageResponse } from "next/og";

/**
 * Shared OG image template so every marketing route uses the same brand
 * language. Each route picks an `eyebrow`, a `title` and a short `tagline`,
 * plus a footer URL slug — the rest of the visual treatment stays consistent.
 */

export const OG_SIZE = { width: 1200, height: 630 } as const;
export const OG_CONTENT_TYPE = "image/png" as const;

type OgInput = {
  eyebrow: string;
  title: string;
  tagline: string;
  pathname: string;
};

export function renderOg({ eyebrow, title, tagline, pathname }: OgInput) {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          background: "#FAFAF7",
          color: "#0F1216",
          padding: "80px",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div
            style={{
              width: 56,
              height: 56,
              borderRadius: 14,
              background: "linear-gradient(135deg,#0E5B4A,#34d3a7)",
              color: "white",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 28,
              fontWeight: 700,
            }}
          >
            Q
          </div>
          <div style={{ fontSize: 26, fontWeight: 600, letterSpacing: -0.5 }}>
            QUATA Digital
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          <div
            style={{
              fontSize: 24,
              color: "#5B6470",
              textTransform: "uppercase",
              letterSpacing: 4,
              fontWeight: 600,
            }}
          >
            {eyebrow}
          </div>
          <div
            style={{
              fontSize: 96,
              fontWeight: 700,
              letterSpacing: -3,
              lineHeight: 1,
              maxWidth: 980,
              background: "linear-gradient(135deg,#0E5B4A,#34d3a7)",
              backgroundClip: "text",
              color: "transparent",
            }}
          >
            {title}
          </div>
          <div
            style={{
              fontSize: 32,
              color: "#0F1216",
              maxWidth: 980,
              lineHeight: 1.25,
            }}
          >
            {tagline}
          </div>
        </div>

        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            color: "#5B6470",
            fontSize: 22,
            borderTop: "1px solid #E7E7E2",
            paddingTop: 24,
          }}
        >
          <div style={{ display: "flex" }}>{`quatadigital.com${pathname}`}</div>
          <div style={{ display: "flex" }}>One ecosystem · Many doorways</div>
        </div>
      </div>
    ),
    { ...OG_SIZE }
  );
}
