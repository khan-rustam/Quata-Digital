import { OG_SIZE, OG_CONTENT_TYPE, renderOg } from "@/lib/og-template";

export const alt = "QUATA Digital — News & insights";
export const size = OG_SIZE;
export const contentType = OG_CONTENT_TYPE;

export default async function Image() {
  return renderOg({
    eyebrow: "News & insights",
    title: "From the team building the rail.",
    tagline:
      "Product launches, market thinking and the inside story of how we're building Africa's digital ecosystem.",
    pathname: "/blog",
  });
}
