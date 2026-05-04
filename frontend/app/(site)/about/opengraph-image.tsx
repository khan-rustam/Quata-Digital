import { OG_SIZE, OG_CONTENT_TYPE, renderOg } from "@/lib/og-template";

export const alt = "About QUATA Digital — Africa's connected operating system";
export const size = OG_SIZE;
export const contentType = OG_CONTENT_TYPE;

export default async function Image() {
  return renderOg({
    eyebrow: "About",
    title: "Built in Africa, for Africa.",
    tagline:
      "Founded May 2025 in Bamenda. Building the connected ecosystem the continent's next decade will run on.",
    pathname: "/about",
  });
}
