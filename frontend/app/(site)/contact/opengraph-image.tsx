import { OG_SIZE, OG_CONTENT_TYPE, renderOg } from "@/lib/og-template";

export const alt = "Contact QUATA Digital";
export const size = OG_SIZE;
export const contentType = OG_CONTENT_TYPE;

export default async function Image() {
  return renderOg({
    eyebrow: "Contact",
    title: "Talk to a real human.",
    tagline:
      "Sales, partnerships, support — write to us in Bamenda. We read everything that comes through.",
    pathname: "/contact",
  });
}
