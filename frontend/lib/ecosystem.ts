export type Product = {
  slug: string;
  name: string;
  tagline: string;
  description: string;
  status: "Live" | "Beta" | "Coming Soon" | "Planned";
  category: string;
  accent: string;
  highlights: string[];
  features: { title: string; body: string }[];
  launch?: string;
  pricing?: string;
};

// Real status confirmed by leadership.
export const products: Product[] = [
  {
    slug: "quatapay",
    name: "QUATAPAY",
    tagline: "All-in-one payments for modern African businesses.",
    description:
      "QUATAPAY is a next-generation payment and financial infrastructure platform designed to enable businesses and individuals across Africa to send, receive and manage money seamlessly. Built for reliability, scalability and local market realities, QUATAPAY brings mobile money, cards and digital financial tools into a unified system — empowering merchants to accept payments, manage transactions and scale without friction.",
    status: "Beta",
    category: "Payments",
    accent: "from-emerald-700 to-emerald-500",
    launch: "Launching May 2026",
    pricing: "Per-transaction with tiered merchant pricing — public + custom enterprise",
    highlights: [
      "Mobile Money + cards in one place",
      "Merchant dashboard with transaction tracking",
      "Payment links and QR-based payments",
    ],
    features: [
      {
        title: "Multi-channel payments",
        body: "Mobile Money (MTN MoMo, Orange Money) and card networks (Visa, Mastercard) — accept it all from one merchant account.",
      },
      {
        title: "Merchant dashboard",
        body: "Real-time transaction tracking, settlement visibility and downloadable reports for finance teams.",
      },
      {
        title: "Payment links & QR",
        body: "Sell anywhere — share a link or print a QR. No website required.",
      },
    ],
  },
  {
    slug: "abaqwa",
    name: "ABAQWA",
    tagline: "Powering smarter business operations across Africa.",
    description:
      "ABAQWA is a business infrastructure platform designed to help businesses manage operations, sales and digital commerce from a single system. It provides tools for inventory management, sales tracking and business analytics — letting teams operate efficiently and make data-driven decisions. Built to integrate seamlessly with QUATAPAY, ABAQWA forms a core part of the QUATA Digital ecosystem.",
    status: "Beta",
    category: "Business operations",
    accent: "from-amber-500 to-amber-300",
    launch: "Launching May 2026",
    pricing: "Subscription-based with tiered plans",
    highlights: [
      "Inventory & sales management",
      "Real-time business analytics",
      "Native QUATAPAY integration",
    ],
    features: [
      {
        title: "Inventory & sales",
        body: "Track stock, sales and orders in one place — no spreadsheets required.",
      },
      {
        title: "Analytics that explain",
        body: "Live dashboards showing what's selling, what's slow and what to restock.",
      },
      {
        title: "Built for QUATAPAY",
        body: "Every transaction recorded in ABAQWA settles through QUATAPAY automatically.",
      },
    ],
  },
  {
    slug: "quatafood",
    name: "QUATAFOOD",
    tagline: "Food delivery and commerce made simple.",
    description:
      "QUATAFOOD is a food ordering and delivery platform connecting customers with restaurants and food vendors in one seamless digital experience. It simplifies food commerce by bringing ordering, payment and delivery coordination into a single system tailored for African cities.",
    status: "Coming Soon",
    category: "Food",
    accent: "from-rose-500 to-orange-400",
    launch: "Q3 2026",
    pricing: "Commission per order",
    highlights: [
      "Online food ordering",
      "Vendor onboarding platform",
      "Integrated payments via QUATAPAY",
    ],
    features: [
      {
        title: "Order, pay, deliver",
        body: "Customers browse menus, pay with QUATAPAY and track delivery in real time.",
      },
      {
        title: "Vendor onboarding",
        body: "Restaurants and kitchens go live in days, not months.",
      },
      {
        title: "Delivery coordination",
        body: "Built-in dispatch keeps couriers and orders in sync.",
      },
    ],
  },
  {
    slug: "88basket",
    name: "88BASKET",
    tagline: "Your everyday shopping, reimagined.",
    description:
      "88BASKET is an e-commerce platform designed to provide a seamless shopping experience for everyday goods, connecting customers with sellers through a modern digital marketplace.",
    status: "Planned",
    category: "Commerce",
    accent: "from-sky-600 to-cyan-400",
    launch: "TBA",
    pricing: "Commission-based",
    highlights: ["Online marketplace", "Vendor onboarding", "Integrated checkout"],
    features: [
      {
        title: "Marketplace at scale",
        body: "Designed to handle daily-essentials commerce across African cities.",
      },
      {
        title: "Easy vendor onboarding",
        body: "List products, manage stock and start selling fast.",
      },
      {
        title: "QUATAPAY checkout",
        body: "Native payment integration so customers complete in one tap.",
      },
    ],
  },
  {
    slug: "88brickz",
    name: "88BRICKZ",
    tagline: "Digital infrastructure for modern real estate.",
    description:
      "88BRICKZ is a real estate technology platform designed to simplify property discovery, transactions and management — bringing transparency and efficiency to the African real estate sector.",
    status: "Coming Soon",
    category: "Real Estate",
    accent: "from-indigo-600 to-violet-500",
    launch: "Q4 2026",
    pricing: "Listing fees + transaction-based",
    highlights: [
      "Verified property listings",
      "Digital transaction support",
      "Property management tools",
    ],
    features: [
      {
        title: "Trust-first listings",
        body: "Verified properties, clear documents, transparent pricing.",
      },
      {
        title: "Digital transactions",
        body: "Move from enquiry to closing without leaving the platform.",
      },
      {
        title: "Property management",
        body: "Tools for landlords and managers — leases, payments, maintenance.",
      },
    ],
  },
  {
    slug: "o3mall",
    name: "O3MALL",
    tagline: "The future of digital marketplaces.",
    description:
      "O3MALL is a large-scale digital commerce platform that brings together multiple vendors and services into a unified online marketplace experience.",
    status: "Planned",
    category: "Commerce",
    accent: "from-fuchsia-600 to-pink-400",
    launch: "TBA",
    pricing: "Commission + subscription options",
    highlights: ["Multi-vendor marketplace", "Digital storefronts", "Centralised management"],
    features: [
      {
        title: "Multi-vendor by design",
        body: "Brands and sellers operate inside one connected mall experience.",
      },
      {
        title: "Storefronts that work",
        body: "Each brand gets a real digital storefront — not just a listing.",
      },
      {
        title: "Centralised management",
        body: "Inventory, orders and payouts handled from one back-office.",
      },
    ],
  },
  {
    slug: "qmediq",
    name: "QMEDIQ",
    tagline: "Digital healthcare access, simplified.",
    description:
      "QMEDIQ is a digital healthcare platform aimed at improving access to medical services, consultations and healthcare management through technology.",
    status: "Planned",
    category: "Health",
    accent: "from-teal-600 to-emerald-400",
    launch: "TBA",
    pricing: "Subscription / service-based",
    highlights: [
      "Digital health access",
      "Appointment management",
      "Healthcare service integration",
    ],
    features: [
      {
        title: "Care, on demand",
        body: "Access to consultations and care without the queues.",
      },
      {
        title: "Appointment management",
        body: "Book, reschedule and pay for appointments in one place.",
      },
      {
        title: "Service integration",
        body: "Plug into pharmacies, labs and providers across the network.",
      },
    ],
  },
];

export function getProduct(slug: string) {
  return products.find((p) => p.slug === slug);
}
