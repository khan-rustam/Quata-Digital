export type ProductFAQ = { q: string; a: string };

export type ProductMetric = {
  value: string;
  label: string;
};

export type ProductUseCase = {
  title: string;
  body: string;
};

export type ProductIntegration = {
  name: string;
  body: string;
};

export type Product = {
  slug: string;
  name: string;
  tagline: string;
  /** Short marketing line used on the hero subtitle. */
  shortDescription: string;
  /** Long-form overview used on the dedicated product page. */
  description: string;
  status: "Live" | "Beta" | "Coming Soon" | "Planned";
  category: string;
  /** Tailwind gradient classes used for the brand strip on cards / hero. */
  accent: string;
  /** Path under /public to the brand logo (square, transparent SVG). */
  logo: string;
  /** Bullet highlights shown on the product card and overview. */
  highlights: string[];
  /** Detailed feature breakdown shown on the product page. */
  features: { title: string; body: string }[];
  /** Audiences who get the most out of this product. */
  useCases: ProductUseCase[];
  /** Other QUATA products / external systems this product talks to. */
  integrations: ProductIntegration[];
  /** Product-specific FAQ entries. */
  faqs: ProductFAQ[];
  /** Numbers shown in the stats strip on the product page. */
  metrics: ProductMetric[];
  /** Public availability copy. */
  launch?: string;
  /** Publicly stated pricing model. */
  pricing?: string;
  /** Optional URL to live product or marketing site. */
  websiteUrl?: string;
};

// Real status confirmed by leadership.
export const products: Product[] = [
  {
    slug: "quatapay",
    name: "QUATAPAY",
    tagline: "All-in-one payments for modern African businesses.",
    shortDescription:
      "Mobile money, cards and wallets — unified into one merchant account with real-time settlement visibility.",
    description:
      "QUATAPAY is a next-generation payment and financial infrastructure platform designed to enable businesses and individuals across Africa to send, receive and manage money seamlessly. Built for reliability, scalability and local market realities, QUATAPAY brings mobile money, cards and digital financial tools into a unified system — empowering merchants to accept payments, manage transactions and scale without friction.",
    status: "Beta",
    category: "Payments",
    accent: "from-blue-800 to-sky-400",
    logo: "/ecosystem/logos/Quata-Pay.png",
    launch: "Launching May 2026",
    pricing: "Per-transaction with tiered merchant pricing — public + custom enterprise",
    highlights: [
      "Mobile Money + cards in one place",
      "Merchant dashboard with transaction tracking",
      "Payment links and QR-based payments",
    ],
    features: [
      {
        title: "Multi-channel acceptance",
        body: "Accept MTN MoMo, Orange Money, Visa and Mastercard from one merchant account. No separate gateways, no separate settlements.",
      },
      {
        title: "Merchant dashboard",
        body: "Real-time transaction tracking, settlement visibility, refund tooling and downloadable reports for finance teams.",
      },
      {
        title: "Payment links & QR",
        body: "Sell anywhere — share a link or print a QR. No website required and no checkout to build.",
      },
      {
        title: "Developer APIs & webhooks",
        body: "Clean REST APIs, signed webhooks and SDKs in JavaScript and Python so you can ship a checkout in an afternoon.",
      },
      {
        title: "Reliability & risk controls",
        body: "Idempotent transfers, duplicate-payment guards and per-merchant velocity rules baked into the rail.",
      },
      {
        title: "Settlement & payouts",
        body: "Same-day settlement on supported corridors with automated payouts to bank or wallet.",
      },
    ],
    useCases: [
      {
        title: "Retail & SMBs",
        body: "Replace cash and disjointed gateways with one terminal, one dashboard and one settlement window.",
      },
      {
        title: "Online merchants",
        body: "Embed checkout, payment links or QR codes — no PCI scope to manage on your side.",
      },
      {
        title: "Marketplaces & platforms",
        body: "Split payments between vendors, hold funds in escrow and orchestrate payouts from one API.",
      },
    ],
    integrations: [
      { name: "ABAQWA", body: "Every transaction recorded in ABAQWA settles through QUATAPAY automatically." },
      { name: "QUATAFOOD", body: "Powers in-app checkout for restaurants and customers." },
      { name: "88BASKET / O3MALL", body: "Native marketplace checkout with multi-vendor splits." },
    ],
    faqs: [
      {
        q: "Which mobile money networks do you support?",
        a: "MTN Mobile Money and Orange Money are first-class at launch. Additional networks roll out by corridor in 2026.",
      },
      {
        q: "How fast does money settle to my bank?",
        a: "Same-day on supported corridors and T+1 elsewhere. Settlement windows are confirmed during onboarding.",
      },
      {
        q: "Do I need to be PCI-compliant?",
        a: "No. QUATAPAY hosts the card surface, so your servers stay outside PCI scope.",
      },
      {
        q: "Can I use QUATAPAY without the rest of the ecosystem?",
        a: "Yes. QUATAPAY is fully usable on its own — the other products simply plug in if you want them later.",
      },
    ],
    metrics: [
      { value: "<1s", label: "Wallet transfer" },
      { value: "99.95%", label: "Operational uptime SLA" },
      { value: "MoMo + Cards", label: "Channels supported" },
      { value: "Same-day", label: "Settlement window" },
    ],
  },
  {
    slug: "abaqwa",
    name: "ABAQWA",
    tagline: "Powering smarter business operations across Africa.",
    shortDescription:
      "One system for inventory, sales, orders and analytics — wired into QUATAPAY out of the box.",
    description:
      "ABAQWA is a business infrastructure platform designed to help businesses manage operations, sales and digital commerce from a single system. It provides tools for inventory management, sales tracking and business analytics — letting teams operate efficiently and make data-driven decisions. Built to integrate seamlessly with QUATAPAY, ABAQWA forms a core part of the QUATA Digital ecosystem.",
    status: "Beta",
    category: "Business operations",
    accent: "from-lime-500 to-yellow-300",
    logo: "/ecosystem/logos/Abaqwa-logo.png",
    launch: "Launching May 2026",
    pricing: "Subscription-based with tiered plans",
    highlights: [
      "Inventory & sales management",
      "Real-time business analytics",
      "Native QUATAPAY integration",
    ],
    features: [
      {
        title: "Inventory & stock control",
        body: "Track stock levels, reorder points and movement across locations — no spreadsheets required.",
      },
      {
        title: "Sales & order management",
        body: "Capture sales from POS, online and field staff in one place, with full order history per customer.",
      },
      {
        title: "Live business analytics",
        body: "Dashboards showing what's selling, what's slow and what to restock — refreshed in real time.",
      },
      {
        title: "Team & role management",
        body: "Invite staff with scoped permissions — per-store, per-product, per-action.",
      },
      {
        title: "Native QUATAPAY checkout",
        body: "Every order can be paid with QUATAPAY, with the receipt and settlement reconciled automatically.",
      },
      {
        title: "Reports & exports",
        body: "Sales, tax and stock reports exportable to CSV/PDF for accountants and tax filings.",
      },
    ],
    useCases: [
      {
        title: "Retail stores",
        body: "Replace cashbooks and Excel with a unified POS, stock and reporting suite.",
      },
      {
        title: "Restaurants & kiosks",
        body: "Track menu performance and food cost while QUATAFOOD pushes online orders into the same back-office.",
      },
      {
        title: "Wholesalers & distributors",
        body: "Manage multi-location stock, orders and credit lines without juggling vendors.",
      },
    ],
    integrations: [
      { name: "QUATAPAY", body: "Every transaction in ABAQWA settles via QUATAPAY out of the box." },
      { name: "QUATAFOOD", body: "Online food orders flow back into the merchant's ABAQWA inventory." },
      { name: "88BASKET", body: "Stock and pricing sync between marketplace listings and ABAQWA." },
    ],
    faqs: [
      {
        q: "Do I need to use QUATAPAY to use ABAQWA?",
        a: "It's recommended for the integrated experience, but ABAQWA also works with cash and external payment methods.",
      },
      {
        q: "Does ABAQWA work offline?",
        a: "POS sales can be captured offline and sync when connectivity returns.",
      },
      {
        q: "How many staff can I invite?",
        a: "Tier-based — see pricing. Roles and permissions are unlimited on every tier.",
      },
    ],
    metrics: [
      { value: "1", label: "System for ops + sales" },
      { value: "Real-time", label: "Inventory updates" },
      { value: "Multi-store", label: "Locations supported" },
      { value: "Native", label: "QUATAPAY integration" },
    ],
  },
  {
    slug: "quatafood",
    name: "QUATAFOOD",
    tagline: "Food delivery and commerce made simple.",
    shortDescription:
      "Order, pay and track delivery — for the customers, restaurants and couriers of African cities.",
    description:
      "QUATAFOOD is a food ordering and delivery platform connecting customers with restaurants and food vendors in one seamless digital experience. It simplifies food commerce by bringing ordering, payment and delivery coordination into a single system tailored for African cities.",
    status: "Coming Soon",
    category: "Food",
    accent: "from-orange-600 to-amber-400",
    logo: "/ecosystem/logos/Quata-Food.png",
    launch: "Q3 2026",
    pricing: "Commission per order + optional promotion fees",
    highlights: [
      "Online food ordering",
      "Vendor onboarding platform",
      "Integrated payments via QUATAPAY",
    ],
    features: [
      {
        title: "Order, pay, deliver",
        body: "Customers browse menus, pay with QUATAPAY and track delivery in real time on a single screen.",
      },
      {
        title: "Vendor onboarding",
        body: "Restaurants and kitchens go live in days — menu builder, stock toggles and operating hours included.",
      },
      {
        title: "Delivery coordination",
        body: "Built-in dispatch keeps couriers and orders in sync, with live ETA and proof-of-delivery.",
      },
      {
        title: "Customer experience",
        body: "Saved addresses, favourite restaurants and re-order in one tap.",
      },
      {
        title: "Promotions & loyalty",
        body: "Vendor-funded discounts, combo deals and loyalty wallet credits stored on QUATAPAY.",
      },
      {
        title: "Vendor analytics",
        body: "See top sellers, peak hours and delivery performance per branch.",
      },
    ],
    useCases: [
      {
        title: "Single-location restaurants",
        body: "Get an online ordering channel without building or maintaining an app.",
      },
      {
        title: "Multi-branch chains",
        body: "Operate every branch from one dashboard with unified menus and settlements.",
      },
      {
        title: "Cloud kitchens & home cooks",
        body: "List a kitchen, accept orders and let QUATAFOOD handle the dispatch.",
      },
    ],
    integrations: [
      { name: "QUATAPAY", body: "Every order is paid through QUATAPAY with split payouts to restaurant + courier." },
      { name: "ABAQWA", body: "Restaurant inventory and sales reflect QUATAFOOD orders in real time." },
    ],
    faqs: [
      {
        q: "When does QUATAFOOD launch?",
        a: "Targeting Q3 2026, starting with major Cameroonian cities.",
      },
      {
        q: "Can a restaurant use its own couriers?",
        a: "Yes. Restaurants can choose between QUATAFOOD's dispatch or their own delivery team.",
      },
      {
        q: "How do payouts work?",
        a: "Daily payouts via QUATAPAY, net of commission and any vendor-funded promotions.",
      },
    ],
    metrics: [
      { value: "Live ETA", label: "Order tracking" },
      { value: "Daily", label: "Vendor payouts" },
      { value: "1 tap", label: "Re-order experience" },
      { value: "Multi-branch", label: "Vendor support" },
    ],
  },
  {
    slug: "88basket",
    name: "88BASKET",
    tagline: "Your everyday shopping, reimagined.",
    shortDescription:
      "An everyday-essentials marketplace built for African cities — vendors, customers and checkout on one rail.",
    description:
      "88BASKET is an e-commerce platform designed to provide a seamless shopping experience for everyday goods, connecting customers with sellers through a modern digital marketplace.",
    status: "Planned",
    category: "Commerce",
    accent: "from-sky-600 to-cyan-400",
    logo: "/ecosystem/logos/88basket.svg",
    launch: "TBA",
    pricing: "Commission-based with optional sponsored placements",
    highlights: ["Online marketplace", "Vendor onboarding", "Integrated checkout"],
    features: [
      {
        title: "Marketplace at scale",
        body: "Designed to handle daily-essentials commerce — groceries, household, electronics — across African cities.",
      },
      {
        title: "Easy vendor onboarding",
        body: "List products, manage stock and start selling fast, with bulk-upload for large catalogues.",
      },
      {
        title: "QUATAPAY checkout",
        body: "Native payment integration so customers complete in one tap and vendors get split payouts.",
      },
      {
        title: "Logistics & fulfilment",
        body: "Choose vendor delivery, third-party fulfilment or 88BASKET dispatch per order.",
      },
      {
        title: "Customer trust signals",
        body: "Verified vendors, transparent reviews and clear refund policies built into the platform.",
      },
    ],
    useCases: [
      {
        title: "Independent sellers",
        body: "List a small catalogue and reach customers without running your own logistics.",
      },
      {
        title: "Brands & distributors",
        body: "Operate a verified storefront with rich analytics and promotions.",
      },
      {
        title: "Daily-essentials shoppers",
        body: "One basket across vendors, paid in one tap with QUATAPAY.",
      },
    ],
    integrations: [
      { name: "QUATAPAY", body: "Single checkout across vendors with automatic split payouts." },
      { name: "ABAQWA", body: "Stock and orders sync with the merchant's ABAQWA back-office." },
    ],
    faqs: [
      {
        q: "When does 88BASKET launch?",
        a: "Date TBA — currently in design and partner-discovery phase.",
      },
      {
        q: "How are vendors verified?",
        a: "KYB checks plus performance signals (delivery time, dispute rate). Details published before launch.",
      },
      {
        q: "Will there be a delivery fee?",
        a: "Yes — calculated per order based on weight, distance and chosen logistics option.",
      },
    ],
    metrics: [
      { value: "1 basket", label: "Across vendors" },
      { value: "Verified", label: "Vendor onboarding" },
      { value: "Native", label: "QUATAPAY checkout" },
      { value: "Multi-mode", label: "Fulfilment" },
    ],
  },
  {
    slug: "88brickz",
    name: "88BRICKZ",
    tagline: "Digital infrastructure for modern real estate.",
    shortDescription:
      "Verified listings, digital transactions and property management — for African real estate done right.",
    description:
      "88BRICKZ is a real estate technology platform designed to simplify property discovery, transactions and management — bringing transparency and efficiency to the African real estate sector.",
    status: "Coming Soon",
    category: "Real Estate",
    accent: "from-blue-900 to-sky-500",
    logo: "/ecosystem/logos/Quata-88Bricks.png",
    launch: "Q4 2026",
    pricing: "Listing fees + transaction-based commission",
    highlights: [
      "Verified property listings",
      "Digital transaction support",
      "Property management tools",
    ],
    features: [
      {
        title: "Trust-first listings",
        body: "Verified properties, clear documents, transparent pricing — no ghost listings, no hidden fees.",
      },
      {
        title: "Digital transactions",
        body: "Move from enquiry to closing without leaving the platform — all paperwork tracked digitally.",
      },
      {
        title: "Property management",
        body: "Tools for landlords and managers — leases, payments, maintenance tickets and tenant comms.",
      },
      {
        title: "Rent & deposit collection",
        body: "Automated rent collection through QUATAPAY with receipts and arrears tracking.",
      },
      {
        title: "Agent & developer dashboards",
        body: "Pipeline view, lead routing and performance analytics for real estate teams.",
      },
    ],
    useCases: [
      {
        title: "Buyers & renters",
        body: "Discover verified properties, compare side-by-side and start the process online.",
      },
      {
        title: "Landlords",
        body: "List units, screen tenants and collect rent in one workspace.",
      },
      {
        title: "Agencies & developers",
        body: "Manage portfolios, leads and transactions across multiple projects.",
      },
    ],
    integrations: [
      { name: "QUATAPAY", body: "Rent, deposits and transactional fees collected via QUATAPAY." },
      { name: "ABAQWA", body: "Agency back-office reporting via ABAQWA dashboards." },
    ],
    faqs: [
      {
        q: "How are listings verified?",
        a: "Document review (title / lease) and physical or virtual inspection before a listing goes live.",
      },
      {
        q: "Can I collect rent through 88BRICKZ?",
        a: "Yes — automated rent collection via QUATAPAY is supported at launch.",
      },
      {
        q: "When does 88BRICKZ go live?",
        a: "Targeting Q4 2026, starting with selected Cameroonian cities.",
      },
    ],
    metrics: [
      { value: "Verified", label: "Listings only" },
      { value: "Digital", label: "Transaction flow" },
      { value: "Built-in", label: "Rent collection" },
      { value: "Q4 2026", label: "Target launch" },
    ],
  },
  {
    slug: "o3mall",
    name: "O3MALL",
    tagline: "The future of digital marketplaces.",
    shortDescription:
      "A multi-vendor digital mall — premium storefronts, unified checkout and centralised back-office.",
    description:
      "O3MALL is a large-scale digital commerce platform that brings together multiple vendors and services into a unified online marketplace experience.",
    status: "Planned",
    category: "Commerce",
    accent: "from-emerald-600 to-green-400",
    logo: "/ecosystem/logos/Quata-Mall.png",
    launch: "TBA",
    pricing: "Commission + optional subscription tiers for premium storefronts",
    highlights: ["Multi-vendor marketplace", "Digital storefronts", "Centralised management"],
    features: [
      {
        title: "Multi-vendor by design",
        body: "Brands and sellers operate inside one connected mall experience with shared discovery.",
      },
      {
        title: "Storefronts that work",
        body: "Each brand gets a real digital storefront — not just a listing — with branding, hero, banners and offers.",
      },
      {
        title: "Centralised management",
        body: "Inventory, orders and payouts handled from one back-office.",
      },
      {
        title: "Unified checkout",
        body: "Customers buy across vendors in one cart with split payouts via QUATAPAY.",
      },
      {
        title: "Promotions & merchandising",
        body: "Mall-wide events, sponsored placements and category curation tools.",
      },
    ],
    useCases: [
      {
        title: "Premium brands",
        body: "Run a controlled, branded storefront without owning logistics or payments infrastructure.",
      },
      {
        title: "Multi-category retailers",
        body: "Move catalogues to a unified shopping experience with cross-category visibility.",
      },
      {
        title: "Discovery shoppers",
        body: "Browse curated brands inside one mall with a single basket and one checkout.",
      },
    ],
    integrations: [
      { name: "QUATAPAY", body: "Unified split-payout checkout across vendors." },
      { name: "88BASKET", body: "Shared discovery for daily-essentials brands." },
      { name: "ABAQWA", body: "Vendor inventory and reporting through ABAQWA." },
    ],
    faqs: [
      {
        q: "How is O3MALL different from 88BASKET?",
        a: "88BASKET focuses on everyday essentials. O3MALL is a curated, branded mall experience for premium and lifestyle brands.",
      },
      {
        q: "Can I run my own promotions?",
        a: "Yes — vendors run their own promos plus opt into mall-wide events.",
      },
      {
        q: "When does O3MALL launch?",
        a: "Date TBA — currently in design and partner-discovery phase.",
      },
    ],
    metrics: [
      { value: "Branded", label: "Storefronts" },
      { value: "1 basket", label: "Across vendors" },
      { value: "Split payouts", label: "Via QUATAPAY" },
      { value: "Curated", label: "Discovery" },
    ],
  },
  {
    slug: "qmediq",
    name: "QMEDIQ",
    tagline: "Digital healthcare access, simplified.",
    shortDescription:
      "Consultations, appointments and care services — connected through one trusted health platform.",
    description:
      "QMEDIQ is a digital healthcare platform aimed at improving access to medical services, consultations and healthcare management through technology.",
    status: "Planned",
    category: "Health",
    accent: "from-teal-600 to-emerald-400",
    logo: "/ecosystem/logos/qmediq.svg",
    launch: "TBA",
    pricing: "Subscription / per-service pricing",
    highlights: [
      "Digital health access",
      "Appointment management",
      "Healthcare service integration",
    ],
    features: [
      {
        title: "Care, on demand",
        body: "Access to consultations and care without the queues — video, in-person or in-app messaging.",
      },
      {
        title: "Appointment management",
        body: "Book, reschedule and pay for appointments in one place across providers.",
      },
      {
        title: "Service integration",
        body: "Plug into pharmacies, labs and providers across the network with one patient identity.",
      },
      {
        title: "Health records",
        body: "A patient-owned record that travels with them across providers in the network.",
      },
      {
        title: "Insurance & payments",
        body: "Pay through QUATAPAY, claim through partnered insurance — no paperwork at the counter.",
      },
    ],
    useCases: [
      {
        title: "Patients & families",
        body: "Find providers, book consults and keep records in one trusted app.",
      },
      {
        title: "Clinics & doctors",
        body: "Run scheduling, consults and billing without juggling tools.",
      },
      {
        title: "Insurers & employers",
        body: "Offer trusted care benefits with transparent claim flows.",
      },
    ],
    integrations: [
      { name: "QUATAPAY", body: "Consult fees, prescriptions and lab orders paid through QUATAPAY." },
      { name: "ABAQWA", body: "Clinic operations and analytics via ABAQWA dashboards." },
    ],
    faqs: [
      {
        q: "Is QMEDIQ a regulated healthcare provider?",
        a: "QMEDIQ is a platform that connects patients with regulated providers. Care is delivered by licensed professionals.",
      },
      {
        q: "How are records kept private?",
        a: "Health records are encrypted at rest and in transit, with consented sharing per provider.",
      },
      {
        q: "When does QMEDIQ launch?",
        a: "Date TBA — currently in scoping with healthcare partners.",
      },
    ],
    metrics: [
      { value: "On-demand", label: "Consultations" },
      { value: "1 record", label: "Across providers" },
      { value: "Encrypted", label: "Patient data" },
      { value: "QUATAPAY", label: "Native payments" },
    ],
  },
];

export function getProduct(slug: string): Product | undefined {
  return products.find((p) => p.slug === slug);
}
