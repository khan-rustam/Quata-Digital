"""The QUATA event catalogue.

This is the contract every platform publishes against. An event is a dotted
key (``deposit.successful``) plus the platform that produced it — the key is
deliberately *not* platform-prefixed, so shared lifecycle events
(``user.registered``, ``security.admin_login``, ``infra.high_cpu``) are
defined once and reused by QuataPay, QuataFood, Abaqwa, QuataTrade, QUATA AI
and the Quata Digital website alike.

Adding a platform = adding a row to ``PLATFORMS``. Adding an event = adding a
row to ``EVENTS``. Neither requires touching the dispatcher, the formatter or
the Telegram transport, which is what keeps the architecture modular.

Unknown keys are *not* rejected: ``resolve_event`` derives a sensible spec
from the key's namespace so a platform can ship a new event before this
catalogue catches up. It just won't get a curated label or priority.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Priorities
# ---------------------------------------------------------------------------

PRIORITY_INFO = "info"
PRIORITY_WARNING = "warning"
PRIORITY_IMPORTANT = "important"
PRIORITY_CRITICAL = "critical"

# Ordered low → high. Used for the per-recipient `min_priority` floor.
PRIORITY_ORDER = [PRIORITY_INFO, PRIORITY_WARNING, PRIORITY_IMPORTANT, PRIORITY_CRITICAL]

PRIORITY_BADGE = {
    PRIORITY_INFO: "🟢 INFO",
    PRIORITY_WARNING: "🟡 WARNING",
    PRIORITY_IMPORTANT: "🟠 IMPORTANT",
    PRIORITY_CRITICAL: "🔴 CRITICAL",
}


def priority_rank(priority: str) -> int:
    """Numeric rank for comparison. Unknown priorities sort as INFO."""
    try:
        return PRIORITY_ORDER.index(priority)
    except ValueError:
        return 0


# ---------------------------------------------------------------------------
# Banners — the headline line of the Telegram message
# ---------------------------------------------------------------------------

BANNER_ALERT = "alert"
BANNER_SECURITY = "security"
BANNER_LARGE_TX = "large_transaction"
BANNER_SYSTEM = "system"
BANNER_SUMMARY = "summary"

BANNER_TEXT = {
    BANNER_ALERT: "🔔 QUATA ALERT",
    BANNER_SECURITY: "🚨 SECURITY ALERT",
    BANNER_LARGE_TX: "💰 LARGE TRANSACTION ALERT",
    BANNER_SYSTEM: "❌ SYSTEM ALERT",
    BANNER_SUMMARY: "📊 QUATA DAILY SUMMARY",
}


# ---------------------------------------------------------------------------
# Platforms
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PlatformSpec:
    slug: str
    name: str
    description: str


PLATFORMS: dict[str, PlatformSpec] = {
    p.slug: p
    for p in [
        PlatformSpec("quatapay", "QuataPay", "Wallets, deposits, withdrawals, merchants, KYC."),
        PlatformSpec("quatafood", "QuataFood", "Restaurants, orders, riders, payouts."),
        PlatformSpec("abaqwa", "Abaqwa", "Delivery, ride and parcel requests."),
        PlatformSpec("quatatrade", "QuataTrade", "P2P trades, escrow, crypto and fiat rails."),
        PlatformSpec("quata_ai", "QUATA AI", "AI service health, usage and administration."),
        PlatformSpec(
            "quata_digital",
            "Quata Digital Enterprise",
            "Website enquiries and the admin console.",
        ),
    ]
}

# Platform used when a publisher omits one (in-process emits from this app).
DEFAULT_PLATFORM = "quata_digital"


def platform_name(slug: str) -> str:
    spec = PLATFORMS.get(slug)
    return spec.name if spec else slug


# ---------------------------------------------------------------------------
# Categories — the unit the admin enables/disables in bulk
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CategorySpec:
    slug: str
    name: str
    description: str


CATEGORIES: dict[str, CategorySpec] = {
    c.slug: c
    for c in [
        CategorySpec("user_management", "User management", "Registration, verification, profile and account lifecycle."),
        CategorySpec("security", "Authentication & security", "Admin sessions, failed logins, lockouts and 2FA changes."),
        CategorySpec("wallet", "Wallets & KYC", "Wallet creation/activation and KYC decisions."),
        CategorySpec("transaction", "Transactions", "Deposits, withdrawals, transfers, refunds and disputes."),
        CategorySpec("merchant", "Merchants", "Merchant onboarding, approval, suspension and settlement."),
        CategorySpec("order", "Food orders", "QuataFood restaurant and order lifecycle."),
        CategorySpec("logistics", "Logistics", "Abaqwa delivery, ride and parcel movements."),
        CategorySpec("trading", "Trading & escrow", "QuataTrade trades, escrow and crypto/fiat rails."),
        CategorySpec("ai_ops", "AI operations", "QUATA AI availability, usage and administration."),
        CategorySpec("website", "Website enquiries", "Contact, partnership, investor and career submissions."),
        CategorySpec("infrastructure", "Infrastructure", "Servers, database, storage, queues and unhandled errors."),
        CategorySpec("payment_gateway", "Payment gateways", "MTN MoMo availability, callbacks and settlements."),
        CategorySpec("summary", "Business summaries", "The scheduled daily business report."),
    ]
}


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EventSpec:
    key: str
    label: str
    category: str
    priority: str = PRIORITY_INFO
    banner: str = BANNER_ALERT
    # Default "Status:" line. Publishers may override per event.
    status: str = "SUCCESS"
    # Fields rendered ahead of the generic payload dump, in this order.
    # Purely cosmetic — a missing field is skipped, an extra one still shows.
    fields: tuple = field(default_factory=tuple)


_USER_FIELDS = (
    "full_name", "username", "email", "phone", "country",
    "user_id", "registration_date", "ip_address", "device_type",
)
_TX_FIELDS = (
    "amount", "currency", "fee", "payment_method",
    "transaction_id", "sender", "receiver", "status",
)
_ORDER_FIELDS = (
    "restaurant", "order_number", "customer", "rider",
    "amount", "currency", "delivery_address",
)
_LOGISTICS_FIELDS = (
    "service_type", "customer", "rider", "amount", "currency",
    "pickup_location", "destination",
)
_TRADE_FIELDS = (
    "trade_id", "currency", "amount", "buyer", "seller", "status",
)
_SECURITY_FIELDS = (
    "full_name", "email", "user_id", "role",
    "ip_address", "device_type", "country", "location", "attempts",
)


def _e(*args, **kwargs) -> EventSpec:
    return EventSpec(*args, **kwargs)


_EVENT_LIST: list[EventSpec] = [
    # ---- User management (every platform) ----
    _e("user.registered", "New User Registration", "user_management", PRIORITY_INFO, fields=_USER_FIELDS),
    _e("user.activated", "User Account Activated", "user_management", PRIORITY_INFO, fields=_USER_FIELDS),
    _e("user.email_verified", "Email Verified", "user_management", PRIORITY_INFO, fields=_USER_FIELDS),
    _e("user.phone_verified", "Phone Number Verified", "user_management", PRIORITY_INFO, fields=_USER_FIELDS),
    _e("user.password_reset_requested", "Password Reset Requested", "user_management", PRIORITY_WARNING, status="PENDING", fields=_USER_FIELDS),
    _e("user.password_changed", "Password Changed Successfully", "user_management", PRIORITY_IMPORTANT, fields=_USER_FIELDS),
    _e("user.profile_updated", "User Profile Updated", "user_management", PRIORITY_INFO, fields=_USER_FIELDS),
    _e("user.deactivated", "Account Deactivated", "user_management", PRIORITY_IMPORTANT, status="DEACTIVATED", fields=_USER_FIELDS),
    _e("user.reactivated", "Account Reactivated", "user_management", PRIORITY_IMPORTANT, fields=_USER_FIELDS),
    _e("user.deleted", "Account Deleted", "user_management", PRIORITY_IMPORTANT, status="DELETED", fields=_USER_FIELDS),

    # ---- Authentication & security ----
    _e("security.admin_login", "Admin Login", "security", PRIORITY_IMPORTANT, BANNER_SECURITY, fields=_SECURITY_FIELDS),
    _e("security.admin_logout", "Admin Logout", "security", PRIORITY_INFO, BANNER_SECURITY, fields=_SECURITY_FIELDS),
    _e("security.admin_login_failed", "Failed Admin Login", "security", PRIORITY_WARNING, BANNER_SECURITY, status="FAILED", fields=_SECURITY_FIELDS),
    _e("security.suspicious_login", "Suspicious Login Attempt", "security", PRIORITY_CRITICAL, BANNER_SECURITY, status="BLOCKED", fields=_SECURITY_FIELDS),
    _e("security.multiple_failed_logins", "Multiple Failed Login Attempts", "security", PRIORITY_CRITICAL, BANNER_SECURITY, status="UNDER ATTACK", fields=_SECURITY_FIELDS),
    _e("security.new_device_login", "Login From a New Device", "security", PRIORITY_IMPORTANT, BANNER_SECURITY, fields=_SECURITY_FIELDS),
    _e("security.new_location_login", "Login From a Different Location", "security", PRIORITY_IMPORTANT, BANNER_SECURITY, fields=_SECURITY_FIELDS),
    _e("security.account_locked", "Account Locked", "security", PRIORITY_CRITICAL, BANNER_SECURITY, status="LOCKED", fields=_SECURITY_FIELDS),
    _e("security.two_factor_enabled", "Two-Factor Authentication Enabled", "security", PRIORITY_IMPORTANT, BANNER_SECURITY, fields=_SECURITY_FIELDS),
    _e("security.two_factor_disabled", "Two-Factor Authentication Disabled", "security", PRIORITY_CRITICAL, BANNER_SECURITY, status="DISABLED", fields=_SECURITY_FIELDS),

    # ---- QuataPay · wallets + KYC ----
    _e("wallet.created", "Wallet Created", "wallet", PRIORITY_INFO, fields=_USER_FIELDS),
    _e("wallet.activated", "Wallet Activated", "wallet", PRIORITY_INFO, fields=_USER_FIELDS),
    _e("kyc.submitted", "KYC Submitted", "wallet", PRIORITY_INFO, status="PENDING REVIEW", fields=_USER_FIELDS),
    _e("kyc.approved", "KYC Approved", "wallet", PRIORITY_INFO, fields=_USER_FIELDS),
    _e("kyc.rejected", "KYC Rejected", "wallet", PRIORITY_IMPORTANT, status="REJECTED", fields=_USER_FIELDS),

    # ---- QuataPay · deposits ----
    _e("deposit.initiated", "Deposit Initiated", "transaction", PRIORITY_INFO, status="PENDING", fields=_TX_FIELDS),
    _e("deposit.successful", "Deposit Successful", "transaction", PRIORITY_INFO, fields=_TX_FIELDS),
    _e("deposit.failed", "Deposit Failed", "transaction", PRIORITY_IMPORTANT, status="FAILED", fields=_TX_FIELDS),

    # ---- QuataPay · withdrawals ----
    _e("withdrawal.requested", "Withdrawal Requested", "transaction", PRIORITY_WARNING, status="AWAITING APPROVAL", fields=_TX_FIELDS),
    _e("withdrawal.approved", "Withdrawal Approved", "transaction", PRIORITY_IMPORTANT, fields=_TX_FIELDS),
    _e("withdrawal.completed", "Withdrawal Completed", "transaction", PRIORITY_IMPORTANT, fields=_TX_FIELDS),
    _e("withdrawal.failed", "Withdrawal Failed", "transaction", PRIORITY_IMPORTANT, status="FAILED", fields=_TX_FIELDS),

    # ---- QuataPay · transfers + payments ----
    _e("transfer.wallet_to_wallet", "Wallet-to-Wallet Transfer", "transaction", PRIORITY_INFO, fields=_TX_FIELDS),
    _e("transfer.internal", "Internal Transfer", "transaction", PRIORITY_INFO, fields=_TX_FIELDS),
    _e("payment.merchant", "Merchant Payment", "transaction", PRIORITY_INFO, fields=_TX_FIELDS),
    _e("payment.qr", "QR Payment", "transaction", PRIORITY_INFO, fields=_TX_FIELDS),
    _e("payment.request_accepted", "Payment Request Accepted", "transaction", PRIORITY_INFO, fields=_TX_FIELDS),

    # ---- QuataPay · merchants ----
    _e("merchant.registered", "Merchant Registration", "merchant", PRIORITY_INFO, status="PENDING APPROVAL", fields=_USER_FIELDS),
    _e("merchant.approved", "Merchant Approval", "merchant", PRIORITY_INFO, fields=_USER_FIELDS),
    _e("merchant.suspended", "Merchant Suspension", "merchant", PRIORITY_IMPORTANT, status="SUSPENDED", fields=_USER_FIELDS),
    _e("merchant.settlement_completed", "Merchant Settlement Completed", "merchant", PRIORITY_INFO, fields=_TX_FIELDS),

    # ---- QuataPay · disputes ----
    _e("transaction.refund_issued", "Refund Issued", "transaction", PRIORITY_IMPORTANT, fields=_TX_FIELDS),
    _e("transaction.chargeback", "Chargeback", "transaction", PRIORITY_CRITICAL, status="CHARGEBACK", fields=_TX_FIELDS),
    _e("transaction.dispute_opened", "Transaction Dispute Opened", "transaction", PRIORITY_IMPORTANT, status="DISPUTED", fields=_TX_FIELDS),
    _e("transaction.dispute_resolved", "Transaction Dispute Resolved", "transaction", PRIORITY_INFO, fields=_TX_FIELDS),

    # ---- QuataPay · large transaction ----
    _e("transaction.large", "Large Transaction", "transaction", PRIORITY_CRITICAL, BANNER_LARGE_TX, fields=_TX_FIELDS),

    # ---- QuataFood ----
    _e("restaurant.registered", "Restaurant Registered", "order", PRIORITY_INFO, status="PENDING APPROVAL", fields=_ORDER_FIELDS),
    _e("restaurant.approved", "Restaurant Approved", "order", PRIORITY_INFO, fields=_ORDER_FIELDS),
    _e("restaurant.suspended", "Restaurant Suspended", "order", PRIORITY_IMPORTANT, status="SUSPENDED", fields=_ORDER_FIELDS),
    _e("order.placed", "Customer Placed Order", "order", PRIORITY_INFO, fields=_ORDER_FIELDS),
    _e("order.accepted", "Restaurant Accepted Order", "order", PRIORITY_INFO, fields=_ORDER_FIELDS),
    _e("order.rejected", "Restaurant Rejected Order", "order", PRIORITY_WARNING, status="REJECTED", fields=_ORDER_FIELDS),
    _e("order.preparing", "Food Preparation Started", "order", PRIORITY_INFO, status="IN PROGRESS", fields=_ORDER_FIELDS),
    _e("order.prepared", "Food Prepared", "order", PRIORITY_INFO, status="READY", fields=_ORDER_FIELDS),
    _e("order.rider_assigned", "Rider Assigned", "order", PRIORITY_INFO, fields=_ORDER_FIELDS),
    _e("order.picked_up", "Rider Picked Up Order", "order", PRIORITY_INFO, fields=_ORDER_FIELDS),
    _e("order.delivered", "Order Delivered", "order", PRIORITY_INFO, fields=_ORDER_FIELDS),
    _e("order.cancelled", "Order Cancelled", "order", PRIORITY_WARNING, status="CANCELLED", fields=_ORDER_FIELDS),
    _e("order.refund_processed", "Customer Refund Processed", "order", PRIORITY_IMPORTANT, fields=_ORDER_FIELDS),
    _e("restaurant.payout_completed", "Restaurant Payout Completed", "order", PRIORITY_INFO, fields=_TX_FIELDS),
    _e("promotion.created", "Promotion Campaign Created", "order", PRIORITY_INFO, fields=_ORDER_FIELDS),

    # ---- Abaqwa ----
    _e("delivery.requested", "Delivery Request Created", "logistics", PRIORITY_INFO, fields=_LOGISTICS_FIELDS),
    _e("ride.requested", "Ride Request Created", "logistics", PRIORITY_INFO, fields=_LOGISTICS_FIELDS),
    _e("parcel.requested", "Parcel Request Created", "logistics", PRIORITY_INFO, fields=_LOGISTICS_FIELDS),
    _e("rider.assigned", "Rider Assigned", "logistics", PRIORITY_INFO, fields=_LOGISTICS_FIELDS),
    _e("rider.accepted", "Rider Accepted Request", "logistics", PRIORITY_INFO, fields=_LOGISTICS_FIELDS),
    _e("pickup.completed", "Pickup Completed", "logistics", PRIORITY_INFO, fields=_LOGISTICS_FIELDS),
    _e("delivery.completed", "Delivery Completed", "logistics", PRIORITY_INFO, fields=_LOGISTICS_FIELDS),
    _e("delivery.cancelled", "Delivery Cancelled", "logistics", PRIORITY_WARNING, status="CANCELLED", fields=_LOGISTICS_FIELDS),
    _e("delivery.payment_completed", "Delivery Payment Completed", "logistics", PRIORITY_INFO, fields=_TX_FIELDS),

    # ---- QuataTrade ----
    _e("account.created", "New Account Created", "trading", PRIORITY_INFO, fields=_USER_FIELDS),
    _e("trade.created", "Trade Created", "trading", PRIORITY_INFO, fields=_TRADE_FIELDS),
    _e("trade.accepted", "Trade Accepted", "trading", PRIORITY_INFO, fields=_TRADE_FIELDS),
    _e("trade.completed", "Trade Completed", "trading", PRIORITY_INFO, fields=_TRADE_FIELDS),
    _e("trade.cancelled", "Trade Cancelled", "trading", PRIORITY_WARNING, status="CANCELLED", fields=_TRADE_FIELDS),
    _e("escrow.funded", "Escrow Funded", "trading", PRIORITY_IMPORTANT, fields=_TRADE_FIELDS),
    _e("escrow.released", "Escrow Released", "trading", PRIORITY_IMPORTANT, fields=_TRADE_FIELDS),
    _e("escrow.dispute_opened", "Escrow Dispute Opened", "trading", PRIORITY_CRITICAL, status="DISPUTED", fields=_TRADE_FIELDS),
    _e("crypto.deposit", "Crypto Deposit", "trading", PRIORITY_IMPORTANT, fields=_TX_FIELDS),
    _e("crypto.withdrawal", "Crypto Withdrawal", "trading", PRIORITY_IMPORTANT, fields=_TX_FIELDS),
    _e("fiat.deposit", "Fiat Deposit", "trading", PRIORITY_IMPORTANT, fields=_TX_FIELDS),
    _e("fiat.withdrawal", "Fiat Withdrawal", "trading", PRIORITY_IMPORTANT, fields=_TX_FIELDS),
    _e("trade.large", "Large Trade Activity", "trading", PRIORITY_CRITICAL, BANNER_LARGE_TX, fields=_TRADE_FIELDS),
    _e("trade.suspicious", "Suspicious Trading Activity", "trading", PRIORITY_CRITICAL, BANNER_SECURITY, status="FLAGGED", fields=_TRADE_FIELDS),

    # ---- QUATA AI ----
    _e("ai.service_started", "AI Service Started", "ai_ops", PRIORITY_INFO),
    _e("ai.service_stopped", "AI Service Stopped", "ai_ops", PRIORITY_IMPORTANT, BANNER_SYSTEM, status="STOPPED"),
    _e("ai.restarted", "AI Restarted", "ai_ops", PRIORITY_WARNING, BANNER_SYSTEM),
    _e("ai.unavailable", "AI Unavailable", "ai_ops", PRIORITY_CRITICAL, BANNER_SYSTEM, status="DOWN"),
    _e("ai.api_error", "AI API Error", "ai_ops", PRIORITY_IMPORTANT, BANNER_SYSTEM, status="ERROR"),
    _e("ai.model_updated", "AI Model Updated", "ai_ops", PRIORITY_INFO),
    _e("ai.usage_spike", "AI Usage Spike", "ai_ops", PRIORITY_WARNING, status="SPIKE"),
    _e("ai.system_overload", "AI System Overload", "ai_ops", PRIORITY_CRITICAL, BANNER_SYSTEM, status="OVERLOADED"),
    _e("ai.knowledge_base_updated", "Knowledge Base Updated", "ai_ops", PRIORITY_INFO),
    _e("ai.admin_added", "AI Administrator Added", "ai_ops", PRIORITY_IMPORTANT, BANNER_SECURITY),
    _e("ai.admin_removed", "AI Administrator Removed", "ai_ops", PRIORITY_IMPORTANT, BANNER_SECURITY),

    # ---- Quata Digital Enterprise website ----
    _e("website.contact_submitted", "Contact Form Submitted", "website", PRIORITY_INFO),
    _e("website.partnership_request", "Partnership Request Submitted", "website", PRIORITY_IMPORTANT),
    _e("website.investor_inquiry", "Investor Inquiry Received", "website", PRIORITY_IMPORTANT),
    _e("website.business_inquiry", "Business Inquiry Received", "website", PRIORITY_IMPORTANT),
    _e("website.career_application", "Career Application Received", "website", PRIORITY_INFO),
    _e("website.support_request", "General Support Request Received", "website", PRIORITY_WARNING),
    _e("website.newsletter_subscribed", "Newsletter Subscription", "website", PRIORITY_INFO),

    # ---- Infrastructure & system monitoring ----
    _e("infra.server_offline", "Server Offline", "infrastructure", PRIORITY_CRITICAL, BANNER_SYSTEM, status="OFFLINE"),
    _e("infra.server_restarted", "Server Restarted", "infrastructure", PRIORITY_WARNING, BANNER_SYSTEM, status="RESTARTED"),
    _e("infra.server_recovered", "Server Recovered", "infrastructure", PRIORITY_IMPORTANT, BANNER_SYSTEM, status="RECOVERED"),
    _e("infra.database_disconnected", "Database Disconnected", "infrastructure", PRIORITY_CRITICAL, BANNER_SYSTEM, status="DISCONNECTED"),
    _e("infra.database_backup_completed", "Database Backup Completed", "infrastructure", PRIORITY_INFO, BANNER_SYSTEM),
    _e("infra.database_backup_failed", "Database Backup Failed", "infrastructure", PRIORITY_CRITICAL, BANNER_SYSTEM, status="FAILED"),
    _e("infra.storage_low", "Storage Running Low", "infrastructure", PRIORITY_WARNING, BANNER_SYSTEM, status="LOW"),
    _e("infra.high_cpu", "High CPU Usage", "infrastructure", PRIORITY_WARNING, BANNER_SYSTEM, status="HIGH"),
    _e("infra.high_ram", "High RAM Usage", "infrastructure", PRIORITY_WARNING, BANNER_SYSTEM, status="HIGH"),
    _e("infra.high_disk", "High Disk Usage", "infrastructure", PRIORITY_WARNING, BANNER_SYSTEM, status="HIGH"),
    _e("infra.api_unavailable", "API Unavailable", "infrastructure", PRIORITY_CRITICAL, BANNER_SYSTEM, status="UNAVAILABLE"),
    _e("infra.job_failure", "Background Job Failure", "infrastructure", PRIORITY_IMPORTANT, BANNER_SYSTEM, status="FAILED"),
    _e("infra.queue_failure", "Queue Failure", "infrastructure", PRIORITY_IMPORTANT, BANNER_SYSTEM, status="FAILED"),
    _e("infra.application_error", "Unexpected Application Error", "infrastructure", PRIORITY_IMPORTANT, BANNER_SYSTEM, status="ERROR"),

    # ---- Payment gateway monitoring ----
    _e("gateway.momo_unavailable", "MTN MoMo API Unavailable", "payment_gateway", PRIORITY_CRITICAL, BANNER_SYSTEM, status="UNAVAILABLE"),
    _e("gateway.momo_restored", "MTN MoMo API Restored", "payment_gateway", PRIORITY_IMPORTANT, BANNER_SYSTEM, status="RESTORED"),
    _e("gateway.payment_delayed", "Payment Processing Delayed", "payment_gateway", PRIORITY_WARNING, BANNER_SYSTEM, status="DELAYED"),
    _e("gateway.callback_failure", "Callback Failure", "payment_gateway", PRIORITY_IMPORTANT, BANNER_SYSTEM, status="FAILED"),
    _e("gateway.settlement_completed", "Settlement Completed", "payment_gateway", PRIORITY_INFO),
    _e("gateway.settlement_failed", "Settlement Failed", "payment_gateway", PRIORITY_CRITICAL, BANNER_SYSTEM, status="FAILED"),

    # ---- Scheduled summary ----
    _e("summary.daily", "Daily Business Summary", "summary", PRIORITY_INFO, BANNER_SUMMARY, status="REPORT"),
]

EVENTS: dict[str, EventSpec] = {spec.key: spec for spec in _EVENT_LIST}


# Namespace → category, used to place an event key that isn't in the
# catalogue yet. Keeps a brand-new platform's events routable (and
# toggleable) on day one instead of dropping them into a nameless bucket.
_NAMESPACE_CATEGORY = {
    "user": "user_management",
    "account": "user_management",
    "security": "security",
    "auth": "security",
    "wallet": "wallet",
    "kyc": "wallet",
    "deposit": "transaction",
    "withdrawal": "transaction",
    "transfer": "transaction",
    "payment": "transaction",
    "transaction": "transaction",
    "merchant": "merchant",
    "restaurant": "order",
    "order": "order",
    "promotion": "order",
    "delivery": "logistics",
    "ride": "logistics",
    "parcel": "logistics",
    "pickup": "logistics",
    "rider": "logistics",
    "trade": "trading",
    "escrow": "trading",
    "crypto": "trading",
    "fiat": "trading",
    "ai": "ai_ops",
    "website": "website",
    "infra": "infrastructure",
    "gateway": "payment_gateway",
    "summary": "summary",
}

UNCATEGORISED = "uncategorised"


def resolve_event(event_key: str) -> EventSpec:
    """Look up an event, deriving a fallback spec for unknown keys.

    A platform that publishes ``loyalty.points_awarded`` before we've added
    it here still gets delivered, categorised by namespace, at INFO. This is
    the extension point that lets new platforms connect without a core
    change.
    """
    spec = EVENTS.get(event_key)
    if spec is not None:
        return spec
    namespace = (event_key or "").split(".", 1)[0].lower()
    category = _NAMESPACE_CATEGORY.get(namespace, UNCATEGORISED)
    label = (event_key or "unknown").replace(".", " · ").replace("_", " ").title()
    return EventSpec(key=event_key, label=label, category=category, priority=PRIORITY_INFO)


def category_name(slug: str) -> str:
    spec = CATEGORIES.get(slug)
    return spec.name if spec else slug.replace("_", " ").title()


def events_for_category(category: str) -> list[EventSpec]:
    return [e for e in _EVENT_LIST if e.category == category]
