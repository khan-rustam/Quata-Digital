"""
Seed the database with the default roles, departments, products, sample users,
sample jobs and a few blog posts.

Idempotent — safe to call repeatedly. Run automatically on startup if
SEED_ON_STARTUP=true.

Reflects the real QUATA Digital Enterprise content provided by leadership:
- Founded May 2025 in Bamenda, Cameroon
- Founder & CEO: Clovis Neba
- Active markets: Cameroon (QUATAPAY + ABAQWA launching May 2026)
- ABAQWA is the BUSINESS INFRASTRUCTURE platform (not mobility)
"""
from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.models import (
    AttendanceLog,
    BlogPost,
    BusinessUnit,
    Department,
    Device,
    Job,
    Page,
    Product,
    Role,
    RolePermission,
    User,
)


ROLES = [
    {
        "slug": "super_admin",
        "name": "Super Admin",
        "description": "Unrestricted access to every module.",
        "permissions": ["*"],
    },
    {
        "slug": "admin",
        "name": "Admin",
        "description": "Manage content, partners, careers, staff and devices.",
        "permissions": [
            "content:manage",
            "partners:manage",
            "careers:manage",
            "staff:manage",
            "rbac:manage",
            "devices:manage",
            "activity:view",
            "analytics:view",
            "newsletter:manage",
            "settings:manage",
        ],
    },
    {
        "slug": "manager",
        "name": "Manager",
        "description": "Run a department, approve leave, send messages.",
        "permissions": ["partners:manage", "careers:manage", "staff:manage", "analytics:view"],
    },
    {
        "slug": "team_lead",
        "name": "Team Lead",
        "description": "Lead a team, triage applications and partner requests.",
        "permissions": ["careers:manage", "partners:manage"],
    },
    {
        "slug": "staff",
        "name": "Staff",
        "description": "Standard internal employee.",
        "permissions": [],
    },
    {
        "slug": "intern",
        "name": "Intern",
        "description": "Limited access intern.",
        "permissions": [],
    },
    {
        "slug": "contractor",
        "name": "Contractor",
        "description": "External contractor with scoped access.",
        "permissions": [],
    },
]

# Real QUATA Digital department structure.
DEPARTMENTS = [
    ("engineering", "Engineering"),
    ("product_design", "Product & Design"),
    ("finance", "Finance"),
    ("operations", "Operations"),
    ("marketing", "Marketing & Growth"),
    ("support", "Customer Support"),
    ("legal", "Legal & Compliance"),
    ("hr", "Human Resources"),
    ("field_ops", "Field Operations"),
    ("facilities", "Facilities Management"),
    ("administration", "Administration"),
]


# All seven products with the boss's real status, taglines and descriptions.
# IMPORTANT: ABAQWA is a business infrastructure platform, NOT mobility.
PRODUCTS = [
    {
        "slug": "quatapay",
        "name": "QUATAPAY",
        "tagline": "All-in-one payments for modern African businesses.",
        "description": (
            "QUATAPAY is a next-generation payment and financial infrastructure platform "
            "designed to enable businesses and individuals across Africa to send, receive "
            "and manage money seamlessly. Built for reliability, scalability and local "
            "market realities, QUATAPAY integrates mobile money, cards and digital "
            "financial tools into one unified system — empowering merchants to accept "
            "payments, manage transactions and scale without friction."
        ),
        "category": "Payments",
        "status": "beta",
        "is_published": True,
        "highlights": [
            "Mobile Money + Cards in one place",
            "Merchant dashboard with transaction tracking",
            "Payment links and QR-based payments",
        ],
        "features": [
            {
                "title": "Multi-channel payments",
                "body": "Mobile Money (MTN MoMo, Orange Money) and card networks (Visa, Mastercard) — accept it all from one merchant account.",
            },
            {
                "title": "Merchant dashboard",
                "body": "Real-time transaction tracking, settlement visibility and downloadable reports for finance teams.",
            },
            {
                "title": "Payment links & QR",
                "body": "Sell anywhere — share a link or print a QR. No website required.",
            },
        ],
    },
    {
        "slug": "abaqwa",
        "name": "ABAQWA",
        "tagline": "Powering smarter business operations across Africa.",
        "description": (
            "ABAQWA is a business infrastructure platform designed to help businesses "
            "manage operations, sales and digital commerce from a single system. It "
            "provides tools for inventory management, sales tracking and business "
            "analytics — letting teams operate efficiently and make data-driven "
            "decisions. Built to integrate seamlessly with QUATAPAY, ABAQWA forms a "
            "core part of the QUATA Digital ecosystem."
        ),
        "category": "Business operations",
        "status": "beta",
        "is_published": True,
        "highlights": [
            "Inventory & sales management",
            "Real-time business analytics",
            "Native QUATAPAY integration",
        ],
        "features": [
            {
                "title": "Inventory & sales",
                "body": "Track stock, sales and orders in one place — no spreadsheets required.",
            },
            {
                "title": "Analytics that explain",
                "body": "Live dashboards showing what's selling, what's slow and what to restock.",
            },
            {
                "title": "Built for QUATAPAY",
                "body": "Every transaction recorded in ABAQWA settles through QUATAPAY automatically.",
            },
        ],
    },
    {
        "slug": "quatafood",
        "name": "QUATAFOOD",
        "tagline": "Food delivery and commerce made simple.",
        "description": (
            "QUATAFOOD is a food ordering and delivery platform connecting customers "
            "with restaurants and food vendors in one seamless digital experience. It "
            "simplifies food commerce by bringing ordering, payment and delivery "
            "coordination into a single system tailored for African cities."
        ),
        "category": "Food",
        "status": "coming_soon",
        "is_published": True,
        "highlights": [
            "Online food ordering",
            "Vendor onboarding platform",
            "Integrated payments via QUATAPAY",
        ],
        "features": [
            {"title": "Order, pay, deliver", "body": "Customers browse menus, pay with QUATAPAY and track delivery in real time."},
            {"title": "Vendor onboarding", "body": "Restaurants and kitchens go live in days, not months."},
            {"title": "Delivery coordination", "body": "Built-in dispatch keeps couriers and orders in sync."},
        ],
    },
    {
        "slug": "88basket",
        "name": "88BASKET",
        "tagline": "Your everyday shopping, reimagined.",
        "description": (
            "88BASKET is an e-commerce platform designed to provide a seamless shopping "
            "experience for everyday goods, connecting customers with sellers through "
            "a modern digital marketplace."
        ),
        "category": "Commerce",
        "status": "planned",
        "is_published": True,
        "highlights": [
            "Online marketplace",
            "Vendor onboarding",
            "Integrated checkout",
        ],
        "features": [],
    },
    {
        "slug": "88brickz",
        "name": "88BRICKZ",
        "tagline": "Digital infrastructure for modern real estate.",
        "description": (
            "88BRICKZ is a real estate technology platform designed to simplify "
            "property discovery, transactions and management — bringing transparency "
            "and efficiency to the African real estate sector."
        ),
        "category": "Real Estate",
        "status": "coming_soon",
        "is_published": True,
        "highlights": [
            "Verified property listings",
            "Digital transaction support",
            "Property management tools",
        ],
        "features": [],
    },
    {
        "slug": "o3mall",
        "name": "O3MALL",
        "tagline": "The future of digital marketplaces.",
        "description": (
            "O3MALL is a large-scale digital commerce platform that brings together "
            "multiple vendors and services into a unified online marketplace experience."
        ),
        "category": "Commerce",
        "status": "planned",
        "is_published": True,
        "highlights": [
            "Multi-vendor marketplace",
            "Digital storefronts",
            "Centralised management",
        ],
        "features": [],
    },
    {
        "slug": "qmediq",
        "name": "QMEDIQ",
        "tagline": "Digital healthcare access, simplified.",
        "description": (
            "QMEDIQ is a digital healthcare platform aimed at improving access to "
            "medical services, consultations and healthcare management through technology."
        ),
        "category": "Health",
        "status": "planned",
        "is_published": True,
        "highlights": [
            "Digital health access",
            "Appointment management",
            "Healthcare service integration",
        ],
        "features": [],
    },
]

# Real open role per the boss (only one for now).
# Shared location + closing markdown reused across every open role.
_LOC = "Bamenda, North-West Region, Cameroon"
_LANGS = (
    "## Languages\n\n"
    "English (spoken and written) is mandatory. French and Cameroon Pidgin "
    "English are a strong advantage — candidates who communicate effectively "
    "in English, French and Pidgin will have an added advantage when working "
    "with customers and partners across Cameroon.\n\n"
)

JOBS = [
    {
        "slug": "operations-platform-manager",
        "title": "Operations & Platform Manager",
        "department": "Operations",
        "location": _LOC,
        "employment_type": "Full-time",
        "summary": (
            "Coordinate and supervise day-to-day operations across QUATAPAY, "
            "QUATAFOOD and ABAQWA — driving service quality, partner onboarding "
            "and operational excellence as we scale."
        ),
        "description": (
            "QUATA Digital Enterprise is a technology company building digital "
            "platforms that solve real-world problems across payments, food delivery, "
            "logistics and commerce in Cameroon and Africa — QUATAPAY (payments, "
            "merchant services, wallets, agent network and payment gateway), QUATAFOOD "
            "(food ordering and delivery) and ABAQWA / Go Abaqwa (parcel delivery, "
            "errands and logistics).\n\n"
            "Reporting to the Founder / CEO, the Operations & Platform Manager "
            "coordinates and supervises day-to-day business operations across all three "
            "platforms. You will ensure smooth platform operations, support merchant and "
            "partner onboarding, oversee operational teams, monitor service performance, "
            "resolve escalated issues and work closely with management to improve "
            "efficiency and customer satisfaction.\n\n"
            "## Key performance indicators\n\n"
            "- Merchant, restaurant and delivery-partner onboarding targets achieved\n"
            "- Customer satisfaction levels\n"
            "- Complaint resolution turnaround time\n"
            "- Platform uptime and operational efficiency\n"
            "- Partner retention rate\n"
            "- Monthly operational growth targets\n\n"
            "## Personal attributes\n\n"
            "- Integrity and professionalism\n"
            "- Accountability and a strong work ethic\n"
            "- Leadership potential and initiative\n"
            "- Teamwork and adaptability\n"
            "- Willingness to learn and grow\n\n"
            + _LANGS +
            "## Why join QUATA Digital\n\n"
            "- Help build innovative technology platforms in Cameroon\n"
            "- Work directly with leadership\n"
            "- Professional growth and development opportunities\n"
            "- Exposure to fintech, food delivery, logistics and digital commerce\n"
            "- Contribute to products with national growth potential\n"
        ),
        "responsibilities": [
            "Oversee daily operations of QUATAPAY, QUATAFOOD and ABAQWA and ensure operational processes run efficiently.",
            "Monitor platform performance and service-delivery standards, and recommend solutions to operational challenges.",
            "Coordinate onboarding of merchants, restaurants, businesses, agents and delivery partners.",
            "Maintain strong partner relationships and ensure partners comply with company operational standards.",
            "Monitor customer satisfaction and coordinate resolution of escalated customer complaints with support teams.",
            "Support rider and driver onboarding and monitor delivery service quality and efficiency.",
            "Supervise operational staff, run team meetings and conduct performance reviews.",
            "Prepare weekly and monthly operational reports and track key business performance indicators.",
            "Ensure company policies are followed, support KYC and partner verification, and report operational risks.",
        ],
        "requirements": [
            "HND or Bachelor's degree in Business Administration, Management, Economics, Marketing, Logistics & Supply Chain, Project Management or a related field.",
            "1–3 years of relevant work experience preferred; strong candidates with less experience may be considered.",
            "Experience in fintech, logistics, delivery services, telecoms, banking, retail operations or technology startups is an advantage.",
            "Strong leadership, organizational and decision-making skills.",
            "Excellent communication and problem-solving abilities.",
            "Ability to manage multiple projects simultaneously in a fast-paced startup environment.",
            "Customer-service orientation with analytical and reporting skills.",
            "Proficiency in Microsoft Office and Google Workspace.",
        ],
    },
    {
        "slug": "customer-support-compliance-officer",
        "title": "Customer Support & Compliance Officer",
        "department": "Customer Experience & Compliance",
        "location": _LOC,
        "employment_type": "Full-time",
        "summary": (
            "Be the first line of communication for customers, merchants and partners "
            "— resolving issues, running KYC and verification, and helping maintain "
            "trust and compliance across QUATAPAY, QUATAFOOD and ABAQWA."
        ),
        "description": (
            "QUATA Digital Enterprise builds innovative digital solutions across "
            "payments, food delivery, logistics and digital commerce — QUATAPAY, "
            "QUATAFOOD and ABAQWA / Go Abaqwa.\n\n"
            "Reporting to the Operations & Platform Manager, the Customer Support & "
            "Compliance Officer serves as the first line of communication between "
            "customers, merchants, restaurants, riders, agents and the company. You "
            "will assist users, verify customer information, support KYC processes, "
            "investigate complaints, monitor suspicious activity and help maintain "
            "trust and compliance standards across all our platforms.\n\n"
            "## Key performance indicators\n\n"
            "- Customer satisfaction ratings\n"
            "- Average response and issue-resolution time\n"
            "- Verification turnaround time and number of accounts verified\n"
            "- Complaint resolution rate\n"
            "- Compliance incident reporting accuracy\n"
            "- Customer retention and satisfaction levels\n\n"
            "## Personal attributes\n\n"
            "- Integrity, honesty and professionalism\n"
            "- Empathy, patience and strong listening skills\n"
            "- Attention to detail and accountability\n"
            "- Reliability and a positive attitude\n"
            "- Team spirit\n\n"
            + _LANGS +
            "## Why join QUATA Digital\n\n"
            "- Contribute to platforms serving thousands of users\n"
            "- Exposure to fintech, logistics, food delivery and digital commerce\n"
            "- Professional growth opportunities\n"
            "- Help build trusted digital services in Cameroon\n"
            "- Collaborative, growth-focused work environment\n"
        ),
        "responsibilities": [
            "Respond to customer inquiries via phone, email, social media, live chat and WhatsApp, and provide accurate product information.",
            "Assist customers with account, payment, order, delivery and general platform-usage issues, escalating complex cases appropriately.",
            "Receive, document, track and follow up on customer complaints and disputes until they are resolved.",
            "Review account, merchant, restaurant and rider verification submissions and ensure onboarding requirements are completed.",
            "Monitor platform activity for suspicious behaviour and flag potentially fraudulent transactions.",
            "Support internal compliance procedures and assist with compliance audits and reviews.",
            "QUATAPAY: support wallet, payment and withdrawal inquiries, merchant onboarding verification and payment-dispute resolution.",
            "QUATAFOOD: assist with order concerns, support restaurant onboarding verification and coordinate issue resolution between customers, restaurants and riders.",
            "ABAQWA: assist with parcel-delivery inquiries, support rider onboarding verification and resolve delivery-related complaints.",
            "Maintain accurate customer records and prepare support and compliance reports, documenting recurring issues and trends.",
        ],
        "requirements": [
            "HND or Bachelor's degree in Business Administration, Banking & Finance, Accounting, Economics, Law, Public Administration, Communication, Customer Service Management or a related field.",
            "1–3 years of customer service, compliance, banking, fintech, telecoms, retail or administrative experience preferred; strong fresh graduates are encouraged to apply.",
            "Excellent verbal and written communication and strong customer-service orientation.",
            "Problem-solving and conflict-resolution skills with strong attention to detail.",
            "Ability to maintain confidentiality and keep good records and documentation.",
            "Basic understanding of compliance and verification procedures.",
            "Ability to multitask and manage workloads effectively.",
            "Computer literacy and proficiency in Microsoft Office and Google Workspace.",
        ],
    },
    {
        "slug": "growth-merchant-acquisition-officer",
        "title": "Growth & Merchant Acquisition Officer",
        "department": "Business Development & Growth",
        "location": _LOC,
        "employment_type": "Full-time",
        "summary": (
            "Drive customer acquisition, merchant onboarding, strategic partnerships "
            "and revenue growth across QUATAPAY, QUATAFOOD and ABAQWA."
        ),
        "description": (
            "QUATA Digital Enterprise builds innovative digital platforms that simplify "
            "payments, food delivery, logistics and commerce across Cameroon and Africa "
            "— QUATAPAY, QUATAFOOD and ABAQWA / Go Abaqwa.\n\n"
            "Reporting to the Operations & Platform Manager, the Growth & Merchant "
            "Acquisition Officer identifies, recruits, onboards and supports businesses "
            "that can benefit from our services. You will actively engage merchants, "
            "restaurants, retailers, service providers, institutions and delivery "
            "partners to expand platform adoption and increase transaction volumes.\n\n"
            "## Key performance indicators\n\n"
            "- Merchants, restaurants and ABAQWA business clients onboarded monthly\n"
            "- Merchant activation rate\n"
            "- Monthly transaction growth from onboarded merchants\n"
            "- Revenue growth contribution and merchant retention rate\n"
            "- Partnership development targets achieved\n"
            "- Lead conversion rate\n\n"
            "## Personal attributes\n\n"
            "- Strong ambition, drive and persistence\n"
            "- Professionalism, confidence and integrity\n"
            "- Initiative and excellent interpersonal skills\n"
            "- Adaptability and a positive attitude\n"
            "- Ability to thrive in a startup environment\n\n"
            + _LANGS +
            "## Why join QUATA Digital\n\n"
            "- Contribute directly to the growth of innovative digital platforms\n"
            "- Exposure to fintech, food delivery, logistics and digital commerce\n"
            "- Career growth within a rapidly expanding company\n"
            "- Performance-based recognition and advancement\n"
            "- Build meaningful business relationships across Cameroon\n"
        ),
        "responsibilities": [
            "Identify and recruit new business partners and develop and execute merchant-acquisition strategies.",
            "Promote company products and services, generate leads and build relationships with business owners and decision-makers.",
            "QUATAPAY: recruit merchants to accept payments, promote merchant and payment-gateway solutions and assist with onboarding, activation and retention.",
            "QUATAFOOD: recruit restaurants, cafes, bakeries, fast-food outlets and food vendors and support onboarding and menu setup.",
            "ABAQWA: recruit businesses needing delivery and logistics, targeting e-commerce, retail, pharmacies, supermarkets and service businesses.",
            "Conduct field visits and sales presentations and attend networking events and business meetings.",
            "Build local partnerships and referral networks and represent the company professionally in the community.",
            "Educate merchants on platform usage and follow up with newly onboarded businesses to ensure activation and engagement.",
            "Monitor competitors and market trends, gather merchant feedback and report findings to management.",
            "Maintain accurate lead and onboarding records and submit weekly and monthly business-development reports.",
        ],
        "requirements": [
            "HND or Bachelor's degree in Marketing, Business Administration, Sales Management, Economics, Entrepreneurship, Commerce, Public Relations, Communication or a related field.",
            "1–3 years of experience in sales, marketing, business development, customer acquisition, telecoms, banking, fintech or retail preferred; strong sales talent considered even with limited experience.",
            "Strong sales, negotiation, communication and presentation skills.",
            "Relationship-building and networking skills with a customer-focused mindset.",
            "Goal-oriented, self-motivated and able to work independently.",
            "Problem-solving, time-management and organizational skills.",
            "Proficiency in Microsoft Office and Google Workspace.",
            "Ability to meet targets and deadlines.",
        ],
    },
    {
        "slug": "digital-marketing-community-manager",
        "title": "Digital Marketing & Community Manager",
        "department": "Marketing & Communications",
        "location": _LOC,
        "employment_type": "Full-time",
        "summary": (
            "Grow brand awareness, customer engagement and merchant adoption across "
            "QUATAPAY, QUATAFOOD and ABAQWA through creative content, campaigns and "
            "community management."
        ),
        "description": (
            "QUATA Digital Enterprise builds innovative digital platforms that simplify "
            "payments, food delivery, logistics and commerce across Cameroon and Africa "
            "— QUATAPAY, QUATAFOOD and ABAQWA / Go Abaqwa.\n\n"
            "Reporting to the Operations & Platform Manager, the Digital Marketing & "
            "Community Manager manages our digital presence, creates engaging content, "
            "grows online communities, executes marketing campaigns and helps drive "
            "customer and merchant acquisition — accelerating adoption of QUATAPAY, "
            "QUATAFOOD and ABAQWA across Cameroon.\n\n"
            "## Key performance indicators\n\n"
            "- Social-media audience growth and engagement rate\n"
            "- User acquisition growth and merchant-acquisition support performance\n"
            "- Campaign conversion rates\n"
            "- Website and app traffic growth\n"
            "- Customer retention and brand-awareness indicators\n"
            "- Community satisfaction levels\n\n"
            "## Personal attributes\n\n"
            "- Creativity and curiosity\n"
            "- Professionalism and initiative\n"
            "- Strong communication skills and attention to detail\n"
            "- Adaptability and team spirit\n"
            "- Passion for technology and innovation\n\n"
            "## Familiarity with\n\n"
            "Facebook, Instagram, TikTok, LinkedIn, X (Twitter), WhatsApp Business, "
            "YouTube and Google Business Profile.\n\n"
            + _LANGS +
            "## Why join QUATA Digital\n\n"
            "- Build and grow exciting technology brands from the ground up\n"
            "- Direct impact on customer and merchant growth\n"
            "- Exposure to fintech, logistics, food delivery and digital commerce\n"
            "- Professional development opportunities\n"
            "- Dynamic and innovative startup environment\n"
        ),
        "responsibilities": [
            "Plan and execute digital marketing campaigns and develop strategies to increase user acquisition and engagement.",
            "Manage company social-media accounts, create and publish engaging content and maintain a consistent brand voice.",
            "Respond to comments, messages and community inquiries and escalate customer concerns to the right departments.",
            "Develop content for social media, blogs, newsletters and promotions, including educational content about our products.",
            "Build and nurture online communities and monitor community feedback and customer sentiment.",
            "QUATAPAY: promote digital-payment adoption and the wallet, payment-gateway, agent and merchant solutions.",
            "QUATAFOOD: promote restaurant partners, seasonal offers and campaigns that increase orders and restaurant visibility.",
            "ABAQWA: promote parcel-delivery and logistics services to businesses and individuals, including e-commerce clients.",
            "Create email, SMS and push-notification engagement and promotional campaigns and monitor their effectiveness.",
            "Track marketing performance, prepare weekly and monthly reports and ensure brand consistency across all channels.",
        ],
        "requirements": [
            "HND or Bachelor's degree in Marketing, Digital Marketing, Communication, Public Relations, Journalism, Business Administration, Media Studies, Advertising or a related field.",
            "1–3 years of experience in digital marketing, communications, social-media management or advertising preferred; strong portfolios considered with limited experience.",
            "Social-media management, content-creation and storytelling skills.",
            "Copywriting, community-engagement and customer-interaction skills.",
            "Digital-advertising knowledge and basic graphic-design awareness.",
            "Campaign planning and execution with analytical and reporting skills.",
            "Creativity, time-management and organizational skills.",
        ],
    },
    {
        "slug": "technical-support-qa-engineer",
        "title": "Technical Support & QA Engineer",
        "department": "Technology & Product",
        "location": _LOC,
        "employment_type": "Full-time",
        "summary": (
            "Ensure the reliability, stability, security and quality of our platforms "
            "— testing features, finding bugs, validating releases and supporting "
            "users across QUATAPAY, QUATAFOOD and ABAQWA."
        ),
        "description": (
            "QUATA Digital Enterprise builds innovative digital platforms that simplify "
            "payments, food delivery, logistics and commerce across Cameroon and Africa "
            "— QUATAPAY, QUATAFOOD and ABAQWA / Go Abaqwa.\n\n"
            "Reporting to the Founder / CEO, the Technical Support & QA Engineer tests "
            "software features, identifies bugs, validates releases, supports users with "
            "technical issues and helps maintain high-quality digital experiences across "
            "all our platforms. You will work closely with developers, operations, "
            "customer support and management to ensure systems run efficiently and "
            "reliably.\n\n"
            "## Key performance indicators\n\n"
            "- Bugs identified before production release\n"
            "- Release quality and stability\n"
            "- Technical issue resolution time\n"
            "- Testing coverage completed per release and accuracy of QA reports\n"
            "- Reduction in recurring and user-reported issues\n"
            "- Platform reliability improvements\n\n"
            "## Personal attributes\n\n"
            "- Attention to detail and analytical thinking\n"
            "- Problem-solving ability and curiosity\n"
            "- Professionalism and accountability\n"
            "- Patience, persistence and strong communication\n"
            "- High standards for quality and team collaboration\n\n"
            "## Advantageous skills\n\n"
            "- Experience testing fintech, delivery or logistics platforms\n"
            "- Experience with Android and iOS mobile apps\n"
            "- Knowledge of Postman or similar API-testing tools\n"
            "- Basic SQL knowledge and understanding of cybersecurity best practices\n"
            "- Familiarity with Git and software-deployment workflows\n\n"
            + _LANGS +
            "## Why join QUATA Digital\n\n"
            "- Work on innovative fintech, food-delivery and logistics platforms\n"
            "- Exposure to modern software products and technologies\n"
            "- Direct collaboration with product and development teams\n"
            "- Career growth in technology and product-quality management\n"
            "- Contribute to solutions with national growth potential\n"
        ),
        "responsibilities": [
            "Test mobile apps, web platforms, dashboards and APIs, and create and execute test plans and test cases.",
            "Verify new features before deployment, identify bugs and defects and document and track issues until resolution.",
            "Conduct regression testing before releases and support staging and production release validation.",
            "Provide first-level technical support, investigate reported issues and escalate complex problems to development teams.",
            "QUATAPAY: test wallet transactions and payment flows, validate merchant onboarding and verify deposit, withdrawal, transfer and settlement processes.",
            "QUATAFOOD: test ordering workflows, validate restaurant onboarding and menu management and test delivery assignment, tracking and promotions.",
            "ABAQWA: test parcel booking and delivery workflows, validate rider assignment and verify logistics, tracking and business-delivery integrations.",
            "Maintain issue logs and QA reports, track recurring system issues and collaborate with developers to improve product quality.",
            "Create and maintain testing documentation and user-support guides where necessary.",
        ],
        "requirements": [
            "HND or Bachelor's degree in Computer Science, Software Engineering, Information Technology, Computer Engineering, Information Systems, Cybersecurity or a related field.",
            "1–3 years of experience in software testing, technical support, QA or IT support preferred; strong technical fresh graduates are encouraged to apply.",
            "Understanding of software-testing principles and the software development lifecycle (SDLC).",
            "Bug reporting and issue tracking, with mobile and web application testing experience.",
            "API-testing fundamentals and basic database knowledge.",
            "System-troubleshooting skills and familiarity with QA tools and methodologies.",
            "Ability to write clear technical reports.",
        ],
    },
    {
        "slug": "finance-reconciliation-officer",
        "title": "Finance & Reconciliation Officer",
        "department": "Finance & Accounts",
        "location": _LOC,
        "employment_type": "Full-time",
        "summary": (
            "Safeguard financial accuracy and transparency — reconciling "
            "transactions, verifying settlements and reporting revenue across QUATAPAY, "
            "QUATAFOOD and ABAQWA."
        ),
        "description": (
            "QUATA Digital Enterprise builds innovative digital platforms that simplify "
            "payments, food delivery, logistics and commerce across Cameroon and Africa "
            "— QUATAPAY, QUATAFOOD and ABAQWA / Go Abaqwa. As transaction volumes "
            "grow, financial accuracy, transparency and accountability become "
            "essential.\n\n"
            "Reporting to the Founder / CEO, the Finance & Reconciliation Officer is "
            "responsible for financial record management, transaction reconciliation, "
            "settlement verification, reporting, revenue tracking and operational "
            "financial controls across all our platforms — ensuring accurate "
            "records, timely settlements and compliance with internal financial "
            "procedures.\n\n"
            "## Key performance indicators\n\n"
            "- Reconciliation and settlement accuracy rates\n"
            "- Daily reconciliation completion rate\n"
            "- Financial-reporting accuracy and timeliness\n"
            "- Number of unresolved discrepancies\n"
            "- Audit readiness and documentation quality\n"
            "- Revenue-tracking accuracy and compliance with financial procedures\n\n"
            "## Personal attributes\n\n"
            "- Integrity, honesty and confidentiality\n"
            "- High attention to detail and accountability\n"
            "- Reliability and professionalism\n"
            "- Strong analytical thinking and organizational discipline\n"
            "- Initiative and a continuous-improvement mindset\n\n"
            "## Professional certifications\n\n"
            "Advantageous but not mandatory: CAT, ACCA (partly or fully completed), "
            "CIMA, CPA or other recognized accounting / finance certifications.\n\n"
            + _LANGS +
            "## Why join QUATA Digital\n\n"
            "- Help build one of Cameroon's emerging digital technology ecosystems\n"
            "- Exposure to fintech, logistics, food delivery and digital commerce\n"
            "- Direct involvement in financial systems across multiple platforms\n"
            "- Career growth within a fast-growing organization\n"
            "- Contribute to impactful solutions serving businesses and communities\n"
        ),
        "responsibilities": [
            "Maintain accurate financial records, monitor daily transactions and support preparation of financial reports.",
            "Reconcile daily platform transactions, verify accuracy across systems and investigate discrepancies and exceptions.",
            "Maintain reconciliation records and audit trails and escalate unresolved discrepancies for review.",
            "QUATAPAY: reconcile wallet transactions, deposits, withdrawals, transfers and merchant payments, monitor settlements and track transaction-fee revenue.",
            "QUATAPAY: reconcile mobile-money transactions and assist in monitoring government-fee allocations and payment-gateway financial controls.",
            "QUATAFOOD: reconcile customer payments, verify restaurant settlements and track commissions and service fees.",
            "ABAQWA: reconcile parcel-delivery payments, verify business-account settlements and monitor logistics service revenue.",
            "Prepare daily, weekly and monthly reconciliation and management reports and track platform revenue performance.",
            "Ensure adherence to financial procedures, support audits and compliance reviews and report financial risks and irregularities.",
            "Maintain organized, securely stored financial documentation and support document retrieval for audits.",
        ],
        "requirements": [
            "HND or Bachelor's degree in Accounting, Banking & Finance, Finance, Economics, Business Administration, Commerce, Accounting & Finance or a related field.",
            "1–3 years of experience in accounting, finance, reconciliation, banking operations, auditing or fintech operations preferred; strong academic backgrounds considered with limited experience.",
            "Experience with financial reconciliation processes is highly desirable.",
            "Financial record management, transaction reconciliation and financial reporting skills.",
            "Strong numerical, analytical and problem-solving skills with high attention to detail.",
            "Spreadsheet proficiency (Microsoft Excel or Google Sheets).",
            "Confidentiality, professionalism, time-management and organizational skills.",
            "Advantageous: fintech, mobile-money reconciliation, merchant-settlement and accounting-software experience.",
        ],
    },
    {
        "slug": "field-marketing-merchant-acquisition-representative",
        "title": "Field Marketing & Merchant Acquisition Representative",
        "department": "Business Development & Marketing",
        "location": _LOC,
        "employment_type": "Full-time / Part-time",
        "summary": (
            "Be a frontline ambassador for QUATA Digital — engaging businesses and "
            "customers across Bamenda to promote services, onboard merchants and grow "
            "adoption of QUATAPAY, QUATAFOOD and ABAQWA."
        ),
        "description": (
            "QUATA Digital Enterprise is a fast-growing technology company building "
            "innovative digital platforms that simplify payments, food delivery, "
            "logistics and commerce across Cameroon — QUATAPAY, QUATAFOOD and "
            "ABAQWA / Go Abaqwa.\n\n"
            "Reporting to the Growth & Merchant Acquisition Officer, the Field Marketing "
            "& Merchant Acquisition Representative is a frontline ambassador for the "
            "company. You will engage businesses and customers directly, promote our "
            "services, support onboarding, generate leads and help drive adoption of "
            "QUATAPAY, QUATAFOOD and ABAQWA. This role is ideal for people who enjoy "
            "meeting people, building relationships and working outdoors.\n\n"
            "## Key performance indicators\n\n"
            "- Customers onboarded and app downloads generated\n"
            "- Merchants, restaurants and business clients acquired\n"
            "- Merchant activation rate\n"
            "- Customer-retention contribution\n"
            "- Monthly acquisition targets achieved\n\n"
            "## Personal attributes\n\n"
            "- Integrity, enthusiasm and a professional appearance\n"
            "- Self-motivation and strong interpersonal skills\n"
            "- Reliability and adaptability\n"
            "- Willingness to learn and a positive attitude\n\n"
            "## Compensation & benefits\n\n"
            "- Competitive base allowance / salary (where applicable)\n"
            "- Performance-based commissions and incentives\n"
            "- Training and professional development\n"
            "- Career growth opportunities within QUATA Digital\n\n"
            + _LANGS +
            "## Why join QUATA Digital\n\n"
            "- Gain valuable experience in fintech, digital commerce, logistics and food delivery\n"
            "- Develop sales, marketing and business-development skills\n"
            "- Work in a fast-growing technology environment\n"
            "- Build a rewarding career with opportunities for advancement\n"
        ),
        "responsibilities": [
            "Promote QUATAPAY, QUATAFOOD and ABAQWA to potential users and educate customers on platform benefits and features.",
            "Assist customers with app downloads, registration and onboarding.",
            "Identify and approach potential merchants and recruit them for QUATAPAY payment services.",
            "Recruit restaurants and food vendors for QUATAFOOD and businesses needing delivery and logistics through ABAQWA.",
            "Assist partners through onboarding and activation.",
            "Conduct community outreach and participate in roadshows, exhibitions, activations and promotional events.",
            "Distribute marketing materials and represent the company professionally in public engagements.",
            "Generate qualified business and customer leads, maintain prospect records and follow up with leads.",
            "Build strong relationships with merchants and customers and gather feedback on market trends and competitor activity.",
            "Support promotional campaigns and special offers and contribute to customer-retention efforts.",
        ],
        "requirements": [
            "Minimum: GCE Advanced Level, a professional certificate, a diploma, an HND or a Bachelor's degree — applicants from all academic disciplines are encouraged to apply.",
            "Previous sales, marketing, customer-service or field experience is an advantage but not mandatory; fresh graduates and motivated job seekers are encouraged to apply.",
            "Strong communication skills with confidence and professionalism.",
            "Ability to persuade and influence, with strong customer-service skills.",
            "Basic smartphone and mobile-app usage skills.",
            "Ability to work independently and as part of a team.",
            "Goal-oriented mindset with good time management and a positive attitude.",
        ],
    },
]

# Three real launch posts ready for site go-live.
BLOG_POSTS = [
    {
        "slug": "introducing-quata-digital",
        "title": "Introducing QUATA Digital",
        "excerpt": "Why we're building Africa's connected digital ecosystem — and what's coming.",
        "body": (
            "QUATA Digital was founded in May 2025 in Bamenda, Cameroon with one clear "
            "objective: to build next-generation digital infrastructure tailored for "
            "African markets.\n\n"
            "Across the continent, millions of businesses and individuals operate in a "
            "fragmented digital environment — payments are unreliable, business tools "
            "are disconnected and scaling across markets remains unnecessarily complex. "
            "Global solutions exist but are rarely designed for the realities of African "
            "markets, leaving a critical gap between potential and execution.\n\n"
            "QUATA Digital exists to close that gap. We're building an integrated "
            "ecosystem — payments, business infrastructure, commerce surfaces and more — "
            "designed to make it easier for anyone, anywhere in Africa, to start, run "
            "and scale a business without friction.\n\n"
            "Our flagship platforms QUATAPAY and ABAQWA launch in May 2026. This is the "
            "beginning."
        ),
        "category": "Company",
        "is_published": True,
    },
    {
        "slug": "what-quatapay-will-do",
        "title": "What QUATAPAY will do for African merchants",
        "excerpt": "One merchant account. Mobile Money + cards + payment links + QR. Built for the realities of doing business in Africa.",
        "body": (
            "When QUATAPAY launches in May 2026, it will give African merchants "
            "something the market has been missing: one merchant account that accepts "
            "every meaningful payment method, runs on infrastructure designed for "
            "African networks, and ships with a real dashboard out of the box.\n\n"
            "Mobile Money. Cards. Payment links. QR. One settlement window. One "
            "support team. One merchant dashboard. That's what QUATAPAY will deliver "
            "from day one — and it's just the foundation for everything else we're "
            "building on the rail."
        ),
        "category": "Product",
        "is_published": True,
    },
    {
        "slug": "the-case-for-one-rail",
        "title": "The case for one rail",
        "excerpt": "Why Africa benefits more from a connected digital ecosystem than another standalone app.",
        "body": (
            "The cost of a single transaction in Africa is rarely about the "
            "transaction itself. It's about everything around it — identity, "
            "settlement, last-mile, business operations.\n\n"
            "When those layers are connected, marginal cost collapses. That's the bet "
            "QUATA Digital is making: a payments rail (QUATAPAY), a business "
            "operations layer (ABAQWA), and commerce surfaces (QUATAFOOD, 88BASKET, "
            "88BRICKZ, O3MALL, QMEDIQ) that all share the same identity, the same "
            "wallet and the same support team.\n\n"
            "One rail. Many products. Built for the continent."
        ),
        "category": "Insight",
        "is_published": True,
    },
]

PAGES = [
    {"slug": "about", "title": "About QUATA", "content": "Mission and vision content lives in the page editor.", "is_published": True},
    {"slug": "privacy", "title": "Privacy policy", "content": "Edit privacy policy from the CMS.", "is_published": True},
    {"slug": "terms", "title": "Terms of service", "content": "Edit terms of service from the CMS.", "is_published": True},
]


def upsert_role(db: Session, payload: dict) -> Role:
    role = db.query(Role).filter(Role.slug == payload["slug"]).first()
    if not role:
        role = Role(slug=payload["slug"], name=payload["name"], description=payload["description"])
        db.add(role)
        db.flush()
    role.name = payload["name"]
    role.description = payload["description"]
    existing = {p.permission for p in role.permissions}
    for perm in payload["permissions"]:
        if perm not in existing:
            db.add(RolePermission(role_id=role.id, permission=perm))
    return role


BUSINESS_UNITS = [
    ("corporate-services", "Corporate Services", "Shared enterprise functions (HR, Finance, Legal, Ops, Tech)."),
    ("quatapay", "QuataPay", "Payments business unit."),
    ("quatatrade", "QuataTrade", "Commerce / marketplace business unit."),
    ("quatafood", "QuataFood", "Food ordering & delivery business unit."),
    ("abaqwa", "Abaqwa", "Abaqwa business unit."),
]


def upsert_business_unit(db: Session, slug: str, name: str, description: str, sort_order: int) -> BusinessUnit:
    bu = db.query(BusinessUnit).filter(BusinessUnit.slug == slug).first()
    if not bu:
        bu = BusinessUnit(slug=slug, name=name, description=description, sort_order=sort_order)
        db.add(bu)
        db.flush()
    bu.name = name
    return bu


def upsert_department(db: Session, slug: str, name: str) -> Department:
    d = db.query(Department).filter(Department.slug == slug).first()
    if not d:
        d = Department(slug=slug, name=name)
        db.add(d)
        db.flush()
    d.name = name
    return d


def upsert_user(
    db: Session,
    *,
    email: str,
    full_name: str,
    role_slug: str,
    dept_slug: str | None = None,
    title: str | None = None,
    password: str | None = None,
) -> User:
    u = db.query(User).filter(User.email == email).first()
    role = db.query(Role).filter(Role.slug == role_slug).first()
    dept = db.query(Department).filter(Department.slug == dept_slug).first() if dept_slug else None
    # Force a password reset on first login if we're using the default
    # placeholder. Anyone deploying with an explicit password takes
    # responsibility for it themselves.
    pw = password or "ChangeMe!2026"
    is_default_pw = pw == "ChangeMe!2026"
    if not u:
        u = User(
            email=email,
            full_name=full_name,
            password_hash=hash_password(pw),
            role_id=role.id if role else None,
            department_id=dept.id if dept else None,
            job_title=title,
            status="active",
            is_active=True,
            must_reset_password=is_default_pw,
        )
        db.add(u)
        db.flush()
    else:
        u.full_name = full_name
        u.role_id = role.id if role else u.role_id
        u.department_id = dept.id if dept else u.department_id
        u.job_title = title or u.job_title
    return u


def run_seed(db: Session) -> None:
    # Roles
    for r in ROLES:
        upsert_role(db, r)

    # Business units (HRMS 1F)
    for i, (slug, name, desc) in enumerate(BUSINESS_UNITS):
        upsert_business_unit(db, slug, name, desc, i)
    db.flush()

    # Departments
    for slug, name in DEPARTMENTS:
        upsert_department(db, slug, name)
    db.flush()

    # Real super admin: Clovis Neba, founder & CEO
    upsert_user(
        db,
        email=settings.DEFAULT_ADMIN_EMAIL,
        full_name="Clovis Neba",
        role_slug="super_admin",
        dept_slug="administration",
        title="Founder & CEO",
        password=settings.DEFAULT_ADMIN_PASSWORD,
    )

    # Products
    for p in PRODUCTS:
        existing = db.query(Product).filter(Product.slug == p["slug"]).first()
        if existing:
            for k, v in p.items():
                setattr(existing, k, v)
        else:
            db.add(Product(**p))

    # Jobs (current open roles). Add-only so admin edits are never clobbered.
    for j in JOBS:
        existing = db.query(Job).filter(Job.slug == j["slug"]).first()
        if not existing:
            db.add(Job(**j, is_published=True))

    # Retire the superseded placeholder role if it was seeded previously.
    legacy = (
        db.query(Job)
        .filter(Job.slug == "business-development-partnerships-manager")
        .first()
    )
    if legacy and legacy.is_published:
        legacy.is_published = False

    # Blog launch posts
    admin = db.query(User).filter(User.email == settings.DEFAULT_ADMIN_EMAIL).first()
    for i, post in enumerate(BLOG_POSTS):
        existing = db.query(BlogPost).filter(BlogPost.slug == post["slug"]).first()
        if not existing:
            db.add(
                BlogPost(
                    **post,
                    author_id=admin.id if admin else None,
                    published_at=datetime.now(timezone.utc) - timedelta(days=i * 5),
                )
            )

    # Pages
    for pg in PAGES:
        existing = db.query(Page).filter(Page.slug == pg["slug"]).first()
        if not existing:
            db.add(Page(**pg))

    # NOTE: We deliberately do NOT seed any sample partner requests, applications,
    # devices, attendance logs or fake staff. The platform launches clean —
    # leadership will add real records as they come in.

    db.commit()
