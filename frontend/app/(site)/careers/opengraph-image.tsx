import { OG_SIZE, OG_CONTENT_TYPE, renderOg } from "@/lib/og-template";

export const alt = "Careers at QUATA Digital";
export const size = OG_SIZE;
export const contentType = OG_CONTENT_TYPE;

export default async function Image() {
  return renderOg({
    eyebrow: "Careers",
    title: "Build the rail with us.",
    tagline:
      "Join the team building Africa's connected payments, business operations and commerce ecosystem.",
    pathname: "/careers",
  });
}
