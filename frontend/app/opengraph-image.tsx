import { ImageResponse } from "next/og";
import { getHeroForOg } from "@/lib/og-helpers";

export const alt = "QUATA Digital — Africa's connected operating system";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function Image() {
  // Read the hero from the CMS Home page so social cards stay in sync
  // with whatever the boss publishes. Falls back to the brand default
  // copy if the API is unreachable or the home page is unpublished.
  const hero = await getHeroForOg("home", {
    title: "The connected operating system for Africa's next decade.",
    subtitle: "Payments · Business operations · Commerce — on one rail.",
  });

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          background: "linear-gradient(135deg, #0E5B4A 0%, #1c8a6e 50%, #34d3a7 100%)",
          color: "white",
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
              background: "rgba(255,255,255,0.15)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 28,
              fontWeight: 700,
            }}
          >
            Q
          </div>
          <div style={{ fontSize: 28, fontWeight: 600, letterSpacing: -0.5 }}>QUATA Digital</div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div
            style={{
              fontSize: 76,
              fontWeight: 600,
              letterSpacing: -2,
              lineHeight: 1.05,
              maxWidth: 980,
            }}
          >
            {hero.title}
          </div>
          {hero.subtitle && (
            <div style={{ fontSize: 28, color: "rgba(255,255,255,0.78)", maxWidth: 900 }}>
              {hero.subtitle}
            </div>
          )}
        </div>

        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            color: "rgba(255,255,255,0.7)",
            fontSize: 22,
          }}
        >
          <div>quatadigital.com</div>
          <div>One ecosystem · Seven products</div>
        </div>
      </div>
    ),
    { ...size }
  );
}
