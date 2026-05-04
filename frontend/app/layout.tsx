import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { JsonLd, orgJsonLd } from "@/components/site/jsonld";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://quatadigital.com";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "QUATA Digital — Africa's connected digital ecosystem",
    template: "%s — QUATA Digital",
  },
  description:
    "QUATA Digital is building Africa's connected digital ecosystem — payments, business operations and commerce on one rail. Founded 2025 in Cameroon.",
  keywords: [
    "QUATA Digital",
    "QUATAPAY",
    "ABAQWA",
    "QUATAFOOD",
    "88BASKET",
    "88BRICKZ",
    "O3MALL",
    "QMEDIQ",
    "Africa",
    "Cameroon",
    "fintech",
    "payments",
    "mobile money",
    "business infrastructure",
  ],
  openGraph: {
    title: "QUATA Digital — Africa's connected digital ecosystem",
    description:
      "Payments, business operations and commerce on one rail. Building Africa's connected digital ecosystem from Cameroon.",
    url: SITE_URL,
    siteName: "QUATA Digital",
    type: "website",
    locale: "en",
  },
  twitter: { card: "summary_large_image" },
  alternates: { canonical: SITE_URL },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-background text-foreground">
        <JsonLd data={orgJsonLd} />
        {children}
      </body>
    </html>
  );
}
