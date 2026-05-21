import { ImageResponse } from "next/og";
import { api } from "@/lib/api";

export const alt = "QUATA Digital — open roles";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

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

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          background:
            "linear-gradient(135deg, #0E5B4A 0%, #1c8a6e 55%, #34d3a7 100%)",
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
          <div style={{ fontSize: 26, fontWeight: 600 }}>QUATA · Careers</div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div
            style={{
              fontSize: 22,
              fontWeight: 600,
              letterSpacing: 2,
              textTransform: "uppercase",
              opacity: 0.85,
            }}
          >
            {department}
          </div>
          <div
            style={{
              fontSize: 64,
              fontWeight: 600,
              letterSpacing: -1.5,
              lineHeight: 1.1,
              maxWidth: 1000,
            }}
          >
            {title}
          </div>
        </div>

        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            color: "rgba(255,255,255,0.75)",
            fontSize: 22,
          }}
        >
          <div>
            {location}
            {employment_type ? ` · ${employment_type}` : ""}
          </div>
          <div>quatadigital.com/careers</div>
        </div>
      </div>
    ),
    { ...size }
  );
}
