import {
  Briefcase,
  Building2,
  Coins,
  Users,
  type LucideIcon,
} from "lucide-react";

export type PartnerType = "business" | "strategic" | "investor" | "service";

export type PartnerPath = {
  slug: PartnerType;
  title: string;
  blurb: string;
  description: string;
  icon: LucideIcon;
  perks: string[];
  formFields: FormField[];
  cta: string;
};

export type FormField = {
  name: string;
  label: string;
  type: "text" | "email" | "tel" | "textarea" | "select" | "url";
  placeholder?: string;
  required?: boolean;
  options?: string[];
};

// Real benefits, eligibility and process per QUATA leadership.
export const partnerPaths: PartnerPath[] = [
  {
    slug: "business",
    title: "Business partner",
    blurb: "Merchants, vendors and businesses joining the QUATA ecosystem.",
    description:
      "If you sell goods or services to people or businesses, plug into QUATA to accept payments via QUATAPAY, manage operations with ABAQWA and reach customers across the QUATA ecosystem.",
    icon: Building2,
    perks: [
      "Accept payments via QUATAPAY (Mobile Money, Cards)",
      "Access to ABAQWA business management tools",
      "Increased visibility across the QUATA ecosystem",
      "Early-partner advantages — priority onboarding and competitive pricing",
    ],
    cta: "Apply as a business",
    formFields: [
      { name: "company_name", label: "Business name", type: "text", required: true, placeholder: "e.g. Bamenda Coffee Co." },
      { name: "contact_name", label: "Contact name", type: "text", required: true, placeholder: "Your full name" },
      { name: "email", label: "Email", type: "email", required: true, placeholder: "you@business.com" },
      { name: "phone", label: "Phone (WhatsApp preferred)", type: "tel", placeholder: "+237 6 7000 0000" },
      { name: "country", label: "Country / city", type: "text", required: true, placeholder: "Cameroon, Bamenda" },
      {
        name: "industry",
        label: "Type of business",
        type: "select",
        options: [
          "Retail",
          "Food & Beverage",
          "Hospitality",
          "Health",
          "Education",
          "Logistics",
          "Services",
          "Other",
        ],
        required: true,
      },
      {
        name: "registration",
        label: "Are you a registered business?",
        type: "select",
        options: ["Registered", "Informal", "Prefer not to say"],
      },
      {
        name: "monthly_volume",
        label: "Estimated monthly transaction volume",
        type: "select",
        options: ["Under $10k", "$10k – $100k", "$100k – $1M", "Over $1M", "Not sure"],
      },
      {
        name: "message",
        label: "Anything we should know?",
        type: "textarea",
        placeholder: "Tell us about your business and goals…",
      },
    ],
  },
  {
    slug: "strategic",
    title: "Strategic partner",
    blurb: "Banks, telcos, platforms and infrastructure providers.",
    description:
      "Integrate at the rail level. Strategic partners co-build with QUATA Digital — connecting banking systems, telecom infrastructure, logistics fleets, identity providers and software platforms into the ecosystem.",
    icon: Briefcase,
    perks: [
      "Integration into the QUATA Digital ecosystem",
      "Revenue-sharing opportunities",
      "Co-development of financial and digital infrastructure",
      "Market expansion collaboration",
    ],
    cta: "Open a strategic conversation",
    formFields: [
      { name: "company_name", label: "Organisation name", type: "text", required: true, placeholder: "e.g. MTN Cameroon" },
      { name: "contact_name", label: "Primary contact", type: "text", required: true, placeholder: "Your full name" },
      { name: "role", label: "Your role", type: "text", placeholder: "e.g. Head of Partnerships" },
      { name: "email", label: "Work email", type: "email", required: true, placeholder: "you@organisation.com" },
      { name: "phone", label: "Phone", type: "tel", placeholder: "+237 6 7000 0000" },
      { name: "website", label: "Website", type: "url", placeholder: "https://yourcompany.com" },
      {
        name: "partner_category",
        label: "Partnership category",
        type: "select",
        options: [
          "Bank / Financial institution",
          "Telco / MNO",
          "Logistics / Fleet",
          "Identity / KYC",
          "Software / Platform",
          "Other",
        ],
        required: true,
      },
      {
        name: "technical_contact",
        label: "Technical contact (optional)",
        type: "text",
        placeholder: "Name + email of the tech lead",
      },
      {
        name: "message",
        label: "Proposed partnership",
        type: "textarea",
        required: true,
        placeholder: "What would you like to integrate, build or co-launch?",
      },
    ],
  },
  {
    slug: "investor",
    title: "Investor / Capital partner",
    blurb: "Pre-seed / seed-stage investors backing African digital infrastructure.",
    description:
      "QUATA Digital is privately raising at the pre-seed / seed stage. This is not a public investment marketplace — submit an enquiry and our team will respond with the right next step. The pitch deck is available upon request (NDA optional).",
    icon: Coins,
    perks: [
      "Early-stage access to the QUATA Digital ecosystem",
      "Exposure to multiple high-growth sectors — fintech, commerce, infrastructure",
      "Long-term scalable investment opportunity in African markets",
      "Quarterly investor updates and a direct line to leadership",
    ],
    cta: "Submit investor interest",
    formFields: [
      { name: "name", label: "Your name", type: "text", required: true, placeholder: "Your full name" },
      { name: "email", label: "Email", type: "email", required: true, placeholder: "you@fund.com" },
      { name: "fund_or_org", label: "Fund / organisation", type: "text", placeholder: "e.g. Acme Ventures" },
      {
        name: "investor_type",
        label: "Investor type",
        type: "select",
        options: [
          "Venture capital",
          "Family office",
          "Angel",
          "Strategic / Corporate",
          "Development finance",
          "Other",
        ],
        required: true,
      },
      {
        name: "ticket_size",
        label: "Indicative ticket size",
        type: "select",
        options: [
          "Under $50k",
          "$50k – $250k",
          "$250k – $1M",
          "$1M – $5M",
          "$5M+",
          "Not specified",
        ],
      },
      {
        name: "thesis",
        label: "Investment focus",
        type: "textarea",
        placeholder: "Sectors, geographies, stage and what attracted you to QUATA.",
      },
    ],
  },
  {
    slug: "service",
    title: "Service partner",
    blurb: "Developers, agencies, logistics providers and operators.",
    description:
      "If you're a developer, agency, logistics provider or operator who can help deliver QUATA's products to merchants and customers — apply to join the service partner network.",
    icon: Users,
    perks: [
      "Access to QUATA ecosystem opportunities",
      "Revenue generation through service delivery",
      "Preferred-partner positioning based on performance",
      "Direct engagement with QUATA's operations team",
    ],
    cta: "Join the service network",
    formFields: [
      { name: "full_name", label: "Full name / company", type: "text", required: true, placeholder: "Your name or company" },
      { name: "phone", label: "Phone (WhatsApp)", type: "tel", required: true, placeholder: "+237 6 7000 0000" },
      { name: "email", label: "Email", type: "email", required: true, placeholder: "you@example.com" },
      { name: "city", label: "City / country", type: "text", required: true, placeholder: "Bamenda, Cameroon" },
      {
        name: "expertise",
        label: "Area of expertise",
        type: "select",
        options: [
          "Software development",
          "Design / branding",
          "Marketing / growth",
          "Logistics / delivery",
          "Field operations",
          "Other",
        ],
        required: true,
      },
      {
        name: "portfolio",
        label: "Portfolio or past work (URL)",
        type: "url",
        placeholder: "https://…",
      },
      {
        name: "message",
        label: "Notes",
        type: "textarea",
        placeholder: "Anything else we should know about your experience?",
      },
    ],
  },
];

export function getPartnerPath(slug: string) {
  return partnerPaths.find((p) => p.slug === slug);
}
