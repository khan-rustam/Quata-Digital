import { getHeroForOg } from "@/lib/og-helpers";
import { OG_CONTENT_TYPE, OG_SIZE, renderOg } from "@/lib/og-template";

export const alt = "QUATA Digital — Africa's connected operating system";
export const size = OG_SIZE;
export const contentType = OG_CONTENT_TYPE;

export default async function Image() {
  // Read the hero from the CMS Home page so social cards stay in sync
  // with whatever the boss publishes. Falls back to the brand default
  // copy if the API is unreachable or the home page is unpublished.
  const hero = await getHeroForOg("home", {
    title: "The connected operating system for Africa's next decade.",
    subtitle: "Payments · Business operations · Commerce — on one rail.",
  });

  return renderOg({
    background: "home",
    title: hero.title,
    tagline: hero.subtitle ?? undefined,
    pathname: "",
    footerRight: "One ecosystem · Seven products",
  });
}
