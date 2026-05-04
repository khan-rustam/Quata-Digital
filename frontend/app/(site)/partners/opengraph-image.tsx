import { OG_SIZE, OG_CONTENT_TYPE, renderOg } from "@/lib/og-template";

export const alt = "Partner with QUATA Digital";
export const size = OG_SIZE;
export const contentType = OG_CONTENT_TYPE;

export default async function Image() {
  return renderOg({
    eyebrow: "Partners",
    title: "Plug into the rail.",
    tagline:
      "Business, strategic, investor and service partners — pick the doorway closest to your need.",
    pathname: "/partners",
  });
}
