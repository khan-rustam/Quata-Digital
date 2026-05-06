"""
Seed the database with the default roles, departments, products, sample users,
sample jobs and a few blog posts.

Idempotent — safe to call repeatedly. Run automatically on startup if
SEED_ON_STARTUP=true.

Reflects the real QUATA Digital Enterprise content provided by leadership:
- Founded May 2025 in Bamenda, Cameroon
- Founder & CEO: Neba Clovis Ngwa
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
JOBS = [
    {
        "slug": "business-development-partnerships-manager",
        "title": "Business Development & Partnerships Manager",
        "department": "Marketing & Growth",
        "location": "Bamenda, Cameroon (hybrid)",
        "employment_type": "Full-time",
        "summary": "Drive merchant acquisition, strategic partnerships and ecosystem growth as we approach the launch of QUATAPAY and ABAQWA.",
        "description": (
            "We are looking for a Business Development & Partnerships Manager to drive "
            "merchant acquisition, strategic partnerships and ecosystem growth across "
            "QUATA Digital's products as we approach launch.\n\n"
            "You will own the relationships that put QUATAPAY and ABAQWA in front of "
            "the businesses that will power our launch. You'll work directly with the "
            "founder, the product team and the operations team to shape how merchants "
            "discover, sign up for and succeed with our platform."
        ),
        "responsibilities": [
            "Acquire merchants and onboard businesses onto QUATAPAY and ABAQWA",
            "Build and manage strategic partnerships",
            "Drive product adoption and market expansion",
            "Support go-to-market execution and growth initiatives",
        ],
        "requirements": [
            "Strong communication and negotiation skills",
            "Experience in sales, partnerships or business development",
            "Understanding of digital products or fintech ecosystems",
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

    # Departments
    for slug, name in DEPARTMENTS:
        upsert_department(db, slug, name)
    db.flush()

    # Real super admin: Neba Clovis Ngwa, founder & CEO
    upsert_user(
        db,
        email=settings.DEFAULT_ADMIN_EMAIL,
        full_name="Neba Clovis Ngwa",
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

    # Jobs (just the one real role for now)
    for j in JOBS:
        existing = db.query(Job).filter(Job.slug == j["slug"]).first()
        if not existing:
            db.add(Job(**j, is_published=True))

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
