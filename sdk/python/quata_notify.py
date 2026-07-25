"""QUATA Notification Service client — drop-in, zero dependencies.

Copy this single file into QuataPay / QuataFood / Abaqwa / QuataTrade /
QUATA AI. It is the only code those platforms need in order to feed
@QuataAlertsBot. No platform ever holds a Telegram token.

    from quata_notify import notify

    notify.publish(
        "deposit.successful",
        {"full_name": "John Doe", "amount": 25000, "currency": "XAF"},
        reference="TXN-000245",
    )

Design notes, because they matter in a payments path:

* **Non-blocking.** `publish()` puts the event on an in-process queue and
  returns. A background daemon thread does the HTTP. Your customer's deposit
  never waits on an alert.
* **Never raises.** Every failure is swallowed and counted. An alerting
  outage must not become a transaction outage.
* **Bounded.** The queue has a hard cap; if the notification service is down
  and the queue fills, the oldest events are dropped and counted rather than
  consuming memory until the process dies.
* **Idempotent.** Pass a `dedupe_key` (strongly recommended) and a retried
  publish will not double-alert the administrators.

Configuration, from the environment:

    QUATA_NOTIFY_URL=https://api.quatadigital.com/api/v1/notify/events
    QUATA_PLATFORM=quatapay
    QUATA_INGEST_KEY=<the key issued for this platform>
    QUATA_NOTIFY_SIGN=true          # set false only if the server has signing off
    QUATA_NOTIFY_ENABLED=true       # local kill-switch

Python 3.8+.
"""
from __future__ import annotations

import atexit
import hashlib
import hmac
import json
import logging
import os
import queue
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, Optional


__all__ = ["QuataNotifier", "notify", "publish"]

log = logging.getLogger("quata.notify")


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class QuataNotifier:
    """Async, fire-and-forget publisher for the QUATA Notification Service."""

    def __init__(
        self,
        url: Optional[str] = None,
        platform: Optional[str] = None,
        ingest_key: Optional[str] = None,
        *,
        sign: Optional[bool] = None,
        enabled: Optional[bool] = None,
        timeout: float = 5.0,
        max_queue: int = 1000,
        max_retries: int = 3,
    ):
        self.url = url or os.getenv("QUATA_NOTIFY_URL", "")
        self.platform = (platform or os.getenv("QUATA_PLATFORM", "")).strip().lower()
        self.ingest_key = ingest_key or os.getenv("QUATA_INGEST_KEY", "")
        self.sign = _env_bool("QUATA_NOTIFY_SIGN", True) if sign is None else sign
        self.enabled = _env_bool("QUATA_NOTIFY_ENABLED", True) if enabled is None else enabled
        self.timeout = timeout
        self.max_retries = max_retries

        self._queue: "queue.Queue[Optional[Dict[str, Any]]]" = queue.Queue(maxsize=max_queue)
        self._worker: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._started = False

        # Observability for the host application: expose these on a health
        # endpoint so a silently-broken integration is visible.
        self.stats = {"published": 0, "delivered": 0, "failed": 0, "dropped": 0}

        if self.enabled and not (self.url and self.platform and self.ingest_key):
            log.warning(
                "quata_notify: not configured (need QUATA_NOTIFY_URL, "
                "QUATA_PLATFORM, QUATA_INGEST_KEY); events will be discarded."
            )
            self.enabled = False

    # -- public API --------------------------------------------------------

    def publish(
        self,
        event: str,
        payload: Optional[Dict[str, Any]] = None,
        *,
        reference: Optional[str] = None,
        priority: Optional[str] = None,
        status: Optional[str] = None,
        dedupe_key: Optional[str] = None,
        occurred_at: Optional[datetime] = None,
    ) -> bool:
        """Queue one event. Returns False if it couldn't be queued.

        Never raises, never blocks. See the module docstring for the
        catalogue of event keys, or docs/NOTIFICATIONS.md in the
        QuataDigital repository.
        """
        if not self.enabled:
            return False
        try:
            body: Dict[str, Any] = {"event": event, "payload": payload or {}}
            if reference:
                body["reference"] = str(reference)
            if priority:
                body["priority"] = priority
            if status:
                body["status"] = status
            if dedupe_key:
                body["dedupe_key"] = dedupe_key
            body["occurred_at"] = (occurred_at or datetime.now(timezone.utc)).isoformat()

            self._ensure_worker()
            try:
                self._queue.put_nowait(body)
            except queue.Full:
                # Drop the oldest rather than the newest: during an incident
                # the most recent events are the ones worth having.
                try:
                    self._queue.get_nowait()
                    self.stats["dropped"] += 1
                    self._queue.put_nowait(body)
                except (queue.Empty, queue.Full):
                    self.stats["dropped"] += 1
                    return False
            self.stats["published"] += 1
            return True
        except Exception:  # noqa: BLE001 — alerting must never break the caller
            log.debug("quata_notify: publish failed", exc_info=True)
            return False

    def flush(self, timeout: float = 5.0) -> None:
        """Block until the queue drains (or the timeout elapses).

        Call before a deliberate shutdown so in-flight alerts aren't lost.
        """
        deadline = time.monotonic() + timeout
        while not self._queue.empty() and time.monotonic() < deadline:
            time.sleep(0.05)

    # -- internals ---------------------------------------------------------

    def _ensure_worker(self) -> None:
        if self._started:
            return
        with self._lock:
            if self._started:
                return
            self._worker = threading.Thread(
                target=self._run, name="quata-notify", daemon=True
            )
            self._worker.start()
            atexit.register(self.flush, 3.0)
            self._started = True

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                return
            try:
                self._send_with_retry(item)
            except Exception:  # noqa: BLE001 — the worker must never die
                log.debug("quata_notify: send failed", exc_info=True)
            finally:
                self._queue.task_done()

    def _send_with_retry(self, body: Dict[str, Any]) -> None:
        for attempt in range(1, self.max_retries + 1):
            ok, retryable = self._send_once(body)
            if ok:
                self.stats["delivered"] += 1
                return
            if not retryable or attempt == self.max_retries:
                break
            time.sleep(min(2 ** attempt, 8))
        self.stats["failed"] += 1

    def _send_once(self, body: Dict[str, Any]) -> "tuple[bool, bool]":
        """Returns (ok, retryable)."""
        raw = json.dumps(body).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "X-Quata-Platform": self.platform,
            "X-Quata-Key": self.ingest_key,
        }
        if self.sign:
            stamp = str(int(time.time()))
            signature = hmac.new(
                self.ingest_key.encode("utf-8"),
                f"{stamp}.".encode("utf-8") + raw,
                hashlib.sha256,
            ).hexdigest()
            headers["X-Quata-Timestamp"] = stamp
            headers["X-Quata-Signature"] = signature

        request = urllib.request.Request(self.url, data=raw, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return 200 <= response.status < 300, False
        except urllib.error.HTTPError as exc:
            # 4xx is our own bug (bad key, bad body) — retrying can't fix it
            # and just hammers the service. 5xx is worth another go.
            retryable = exc.code >= 500 or exc.code == 429
            if not retryable:
                log.warning("quata_notify: rejected with HTTP %s", exc.code)
            return False, retryable
        except Exception:  # noqa: BLE001 — network, DNS, timeout
            return False, True


# Module-level default instance, configured from the environment.
notify = QuataNotifier()


def publish(event: str, payload: Optional[Dict[str, Any]] = None, **kwargs) -> bool:
    """Convenience wrapper around the default notifier."""
    return notify.publish(event, payload, **kwargs)


# ---------------------------------------------------------------------------
# Event keys — see docs/NOTIFICATIONS.md for the full catalogue.
# Unknown keys are accepted by the service, so this is a convenience, not a
# constraint.
# ---------------------------------------------------------------------------

class Events:
    # Users (every platform)
    USER_REGISTERED = "user.registered"
    USER_ACTIVATED = "user.activated"
    USER_EMAIL_VERIFIED = "user.email_verified"
    USER_PHONE_VERIFIED = "user.phone_verified"
    USER_PASSWORD_RESET_REQUESTED = "user.password_reset_requested"
    USER_PASSWORD_CHANGED = "user.password_changed"
    USER_PROFILE_UPDATED = "user.profile_updated"
    USER_DEACTIVATED = "user.deactivated"
    USER_REACTIVATED = "user.reactivated"
    USER_DELETED = "user.deleted"

    # Security (every platform)
    ADMIN_LOGIN = "security.admin_login"
    ADMIN_LOGOUT = "security.admin_logout"
    ADMIN_LOGIN_FAILED = "security.admin_login_failed"
    SUSPICIOUS_LOGIN = "security.suspicious_login"
    MULTIPLE_FAILED_LOGINS = "security.multiple_failed_logins"
    NEW_DEVICE_LOGIN = "security.new_device_login"
    NEW_LOCATION_LOGIN = "security.new_location_login"
    ACCOUNT_LOCKED = "security.account_locked"
    TWO_FACTOR_ENABLED = "security.two_factor_enabled"
    TWO_FACTOR_DISABLED = "security.two_factor_disabled"

    # QuataPay
    WALLET_CREATED = "wallet.created"
    WALLET_ACTIVATED = "wallet.activated"
    KYC_SUBMITTED = "kyc.submitted"
    KYC_APPROVED = "kyc.approved"
    KYC_REJECTED = "kyc.rejected"
    DEPOSIT_INITIATED = "deposit.initiated"
    DEPOSIT_SUCCESSFUL = "deposit.successful"
    DEPOSIT_FAILED = "deposit.failed"
    WITHDRAWAL_REQUESTED = "withdrawal.requested"
    WITHDRAWAL_APPROVED = "withdrawal.approved"
    WITHDRAWAL_COMPLETED = "withdrawal.completed"
    WITHDRAWAL_FAILED = "withdrawal.failed"
    TRANSFER_WALLET_TO_WALLET = "transfer.wallet_to_wallet"
    TRANSFER_INTERNAL = "transfer.internal"
    PAYMENT_MERCHANT = "payment.merchant"
    PAYMENT_QR = "payment.qr"
    PAYMENT_REQUEST_ACCEPTED = "payment.request_accepted"
    MERCHANT_REGISTERED = "merchant.registered"
    MERCHANT_APPROVED = "merchant.approved"
    MERCHANT_SUSPENDED = "merchant.suspended"
    MERCHANT_SETTLEMENT_COMPLETED = "merchant.settlement_completed"
    REFUND_ISSUED = "transaction.refund_issued"
    CHARGEBACK = "transaction.chargeback"
    DISPUTE_OPENED = "transaction.dispute_opened"
    DISPUTE_RESOLVED = "transaction.dispute_resolved"

    # QuataFood
    RESTAURANT_REGISTERED = "restaurant.registered"
    RESTAURANT_APPROVED = "restaurant.approved"
    RESTAURANT_SUSPENDED = "restaurant.suspended"
    ORDER_PLACED = "order.placed"
    ORDER_ACCEPTED = "order.accepted"
    ORDER_REJECTED = "order.rejected"
    ORDER_PREPARING = "order.preparing"
    ORDER_PREPARED = "order.prepared"
    ORDER_RIDER_ASSIGNED = "order.rider_assigned"
    ORDER_PICKED_UP = "order.picked_up"
    ORDER_DELIVERED = "order.delivered"
    ORDER_CANCELLED = "order.cancelled"
    ORDER_REFUND_PROCESSED = "order.refund_processed"
    RESTAURANT_PAYOUT_COMPLETED = "restaurant.payout_completed"
    PROMOTION_CREATED = "promotion.created"

    # Abaqwa
    DELIVERY_REQUESTED = "delivery.requested"
    RIDE_REQUESTED = "ride.requested"
    PARCEL_REQUESTED = "parcel.requested"
    RIDER_ASSIGNED = "rider.assigned"
    RIDER_ACCEPTED = "rider.accepted"
    PICKUP_COMPLETED = "pickup.completed"
    DELIVERY_COMPLETED = "delivery.completed"
    DELIVERY_CANCELLED = "delivery.cancelled"
    DELIVERY_PAYMENT_COMPLETED = "delivery.payment_completed"

    # QuataTrade
    ACCOUNT_CREATED = "account.created"
    TRADE_CREATED = "trade.created"
    TRADE_ACCEPTED = "trade.accepted"
    TRADE_COMPLETED = "trade.completed"
    TRADE_CANCELLED = "trade.cancelled"
    ESCROW_FUNDED = "escrow.funded"
    ESCROW_RELEASED = "escrow.released"
    ESCROW_DISPUTE_OPENED = "escrow.dispute_opened"
    CRYPTO_DEPOSIT = "crypto.deposit"
    CRYPTO_WITHDRAWAL = "crypto.withdrawal"
    FIAT_DEPOSIT = "fiat.deposit"
    FIAT_WITHDRAWAL = "fiat.withdrawal"
    TRADE_LARGE = "trade.large"
    TRADE_SUSPICIOUS = "trade.suspicious"

    # QUATA AI
    AI_SERVICE_STARTED = "ai.service_started"
    AI_SERVICE_STOPPED = "ai.service_stopped"
    AI_RESTARTED = "ai.restarted"
    AI_UNAVAILABLE = "ai.unavailable"
    AI_API_ERROR = "ai.api_error"
    AI_MODEL_UPDATED = "ai.model_updated"
    AI_USAGE_SPIKE = "ai.usage_spike"
    AI_SYSTEM_OVERLOAD = "ai.system_overload"
    AI_KNOWLEDGE_BASE_UPDATED = "ai.knowledge_base_updated"
    AI_ADMIN_ADDED = "ai.admin_added"
    AI_ADMIN_REMOVED = "ai.admin_removed"

    # Infrastructure — ❌ SYSTEM ALERT
    SERVER_OFFLINE = "infra.server_offline"
    SERVER_RESTARTED = "infra.server_restarted"
    SERVER_RECOVERED = "infra.server_recovered"
    DATABASE_DISCONNECTED = "infra.database_disconnected"
    DATABASE_BACKUP_COMPLETED = "infra.database_backup_completed"
    DATABASE_BACKUP_FAILED = "infra.database_backup_failed"
    STORAGE_LOW = "infra.storage_low"
    HIGH_CPU = "infra.high_cpu"
    HIGH_RAM = "infra.high_ram"
    HIGH_DISK = "infra.high_disk"
    API_UNAVAILABLE = "infra.api_unavailable"
    JOB_FAILURE = "infra.job_failure"
    QUEUE_FAILURE = "infra.queue_failure"
    APPLICATION_ERROR = "infra.application_error"

    # Payment gateways
    MOMO_UNAVAILABLE = "gateway.momo_unavailable"
    MOMO_RESTORED = "gateway.momo_restored"
    PAYMENT_DELAYED = "gateway.payment_delayed"
    CALLBACK_FAILURE = "gateway.callback_failure"
    SETTLEMENT_COMPLETED = "gateway.settlement_completed"
    SETTLEMENT_FAILED = "gateway.settlement_failed"

    # Scheduled report — publish with {"metrics": {...}} to override the
    # figures the service would otherwise derive from your event stream.
    DAILY_SUMMARY = "summary.daily"


if __name__ == "__main__":  # pragma: no cover — manual smoke test
    print(f"platform={notify.platform!r} url={notify.url!r} enabled={notify.enabled}")
    notify.publish(
        Events.USER_REGISTERED,
        {"full_name": "SDK smoke test", "email": "sdk@example.com", "country": "Cameroon"},
        reference="SDK-TEST",
        dedupe_key=f"sdk-test:{int(time.time())}",
    )
    notify.flush()
    print(notify.stats)
