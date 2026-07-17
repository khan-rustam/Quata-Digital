import { api } from "@/lib/api";
import { OG_CONTENT_TYPE, OG_SIZE, renderOg } from "@/lib/og-template";

export const alt = "QUATA Digital — open roles";
export const size = OG_SIZE;
export const contentType = OG_CONTENT_TYPE;

/**
 * Per-job Open Graph card.
 *
 * Per-role share previews dramatically improve LinkedIn / Twitter
 * click-throughs versus a generic careers OG image.
 */
export default async function JobOgImage({
  params,
}: {
  params: { id: string };
}) {
  let title = "Build Africa's connected digital ecosystem.";
  let department = "QUATA Digital";
  let location = "Cameroon";
  let employment_type = "";
  try {
    const job = await api<{
      title: string;
      department: string;
      location: string;
      employment_type: string;
    }>(`/jobs/${params.id}`);
    title = job.title || title;
    department = job.department || department;
    location = job.location || location;
    employment_type = job.employment_type || "";
  } catch {
    /* keep defaults */
  }

  return renderOg({
    background: "careers",
    eyebrow: department,
    title,
    pathname: "/careers",
    footerLeft: `${location}${employment_type ? ` · ${employment_type}` : ""}`,
    footerRight: "quatadigital.com/careers",
  });
}
