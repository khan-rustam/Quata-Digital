import * as React from "react";

/**
 * Inline JSON-LD script. Use as a server component child anywhere you want
 * structured data. The content is sanitised lightly — no `</script>` allowed.
 */
export function JsonLd({ data }: { data: Record<string, unknown> }) {
  const json = JSON.stringify(data).replace(/</g, "\\u003c");
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: json }}
    />
  );
}

const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://quatadigital.com";

export const orgJsonLd = {
  "@context": "https://schema.org",
  "@type": "Organization",
  name: "QUATA Digital Enterprise",
  legalName: "QUATA Digital Enterprise",
  foundingDate: "2025-05",
  url: SITE,
  logo: `${SITE}/logo.png`,
  description:
    "QUATA Digital is building Africa's connected digital ecosystem — payments, business operations and commerce on one rail.",
  founder: { "@type": "Person", name: "Neba Clovis Ngwa", jobTitle: "Founder & CEO" },
  address: {
    "@type": "PostalAddress",
    addressLocality: "Bamenda",
    addressRegion: "North West Region",
    addressCountry: "CM",
  },
  identifier: [
    { "@type": "PropertyValue", propertyID: "RCCM", value: "RC/BDA/2025A/189" },
    { "@type": "PropertyValue", propertyID: "Tax ID", value: "M052517750267W" },
  ],
  taxID: "M052517750267W",
  sameAs: [
    "https://www.facebook.com/share/1HFDnBuFWz/",
    "https://www.instagram.com/quatadigital",
  ],
  contactPoint: [
    {
      "@type": "ContactPoint",
      email: "info@quatadigital.com",
      contactType: "customer service",
      areaServed: "CM",
      availableLanguage: ["English"],
    },
    {
      "@type": "ContactPoint",
      email: "support@quatadigital.com",
      contactType: "technical support",
      areaServed: "CM",
      availableLanguage: ["English"],
    },
  ],
};

export function productJsonLd(product: {
  slug: string;
  name: string;
  tagline: string;
  description: string;
  category: string;
  logo?: string;
}) {
  return {
    "@context": "https://schema.org",
    "@type": "Product",
    name: product.name,
    category: product.category,
    description: product.description || product.tagline,
    url: `${SITE}/ecosystem/${product.slug}`,
    image: product.logo ? `${SITE}${product.logo}` : undefined,
    brand: { "@type": "Organization", name: "QUATA Digital" },
  };
}

export function jobJsonLd(job: {
  id: number;
  title: string;
  department: string;
  location: string;
  employment_type: string;
  summary: string;
  description?: string;
  created_at?: string;
  published_at?: string;
}) {
  // `datePosted` must be stable across renders or Google flags the
  // posting as constantly re-published. Use the real timestamp from the
  // API; only fall back to "today" if neither field is present.
  const posted = job.published_at || job.created_at || new Date().toISOString();
  return {
    "@context": "https://schema.org",
    "@type": "JobPosting",
    title: job.title,
    description: job.description || job.summary,
    datePosted: posted,
    employmentType: job.employment_type.toUpperCase().replace("-", "_"),
    hiringOrganization: {
      "@type": "Organization",
      name: "QUATA Digital",
      sameAs: SITE,
    },
    jobLocation: {
      "@type": "Place",
      address: { "@type": "PostalAddress", addressLocality: job.location },
    },
    industry: job.department,
    url: `${SITE}/careers/${job.id}`,
  };
}

export function articleJsonLd(post: {
  slug: string;
  title: string;
  excerpt: string;
  published_at: string;
  author?: string;
  category?: string;
}) {
  return {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: post.title,
    description: post.excerpt,
    datePublished: post.published_at,
    author: { "@type": "Person", name: post.author ?? "QUATA Editorial" },
    articleSection: post.category,
    mainEntityOfPage: { "@type": "WebPage", "@id": `${SITE}/blog/${post.slug}` },
  };
}

export function breadcrumbJsonLd(crumbs: { name: string; href: string }[]) {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: crumbs.map((c, i) => ({
      "@type": "ListItem",
      position: i + 1,
      name: c.name,
      item: `${SITE}${c.href}`,
    })),
  };
}
