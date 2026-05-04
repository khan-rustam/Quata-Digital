import { OG_SIZE, OG_CONTENT_TYPE, renderOg } from "@/lib/og-template";

export const alt = "Security at QUATA Digital";
export const size = OG_SIZE;
export const contentType = OG_CONTENT_TYPE;

export default async function Image() {
  return renderOg({
    eyebrow: "Trust & security",
    title: "Safe by default.",
    tagline:
      "Encryption in transit and at rest, full audit trail, regional data residency — the security baseline every product on the rail inherits.",
    pathname: "/security",
  });
}
