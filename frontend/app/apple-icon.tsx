import { ImageResponse } from "next/og";

export const size = { width: 180, height: 180 };
export const contentType = "image/png";

export default function AppleIcon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          background: "linear-gradient(135deg,#0E5B4A,#34d3a7)",
          color: "white",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 110,
          fontWeight: 700,
          fontFamily: "system-ui, sans-serif",
          letterSpacing: -4,
        }}
      >
        Q
      </div>
    ),
    { ...size }
  );
}
