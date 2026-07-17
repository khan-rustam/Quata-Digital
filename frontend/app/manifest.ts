import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "QUATA Digital",
    short_name: "QUATA",
    description:
      "QUATA Digital is building Africa's connected digital ecosystem — payments, business operations and commerce on one rail.",
    start_url: "/",
    scope: "/",
    display: "standalone",
    orientation: "portrait",
    background_color: "#ffffff",
    theme_color: "#006078",
    icons: [
      { src: "/favicon.ico", sizes: "16x16 32x32 48x48", type: "image/x-icon" },
      { src: "/icon.png", sizes: "32x32", type: "image/png" },
      { src: "/icon1.png", sizes: "192x192", type: "image/png" },
      { src: "/icon2.png", sizes: "512x512", type: "image/png" },
      { src: "/apple-icon.png", sizes: "180x180", type: "image/png" },
      {
        src: "/icon-maskable-192.png",
        sizes: "192x192",
        type: "image/png",
        purpose: "maskable",
      },
      {
        src: "/icon-maskable-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
  };
}
