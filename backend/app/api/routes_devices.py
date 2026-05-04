"""
Webhook ingestion for biometric attendance devices.

Devices authenticate with the per-device api_token configured under
/admin/devices.

If DEVICE_REQUIRE_SIGNATURE=true, devices must additionally sign each request:
   message  = f"{X-Device-Timestamp}.{raw_request_body}"
   signature = HMAC-SHA256(device.api_token, message).hexdigest()
"""
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import log_activity
from app.core.config import settings
from app.db.session import get_db
from app.models import AttendanceLog, Device, User
from app.services.security_extras import verify_device_hmac

router = APIRouter(prefix="/devices", tags=["devices"])


class DeviceEvent(BaseModel):
    biometric_id: str
    event: str  # check_in | check_out
    timestamp: Optional[datetime] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class DeviceBatchIn(BaseModel):
    events: List[DeviceEvent]


def _device_from_token(db: Session, device_id: int, token: str | None) -> Device:
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Device not found")
    if not device.api_token or device.api_token != token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid device token")
    return device


@router.post("/{device_id}/sync")
async def device_sync(
    device_id: int,
    request: Request,
    x_device_token: str | None = Header(default=None, alias="X-Device-Token"),
    x_device_signature: str | None = Header(default=None, alias="X-Device-Signature"),
    x_device_timestamp: str | None = Header(default=None, alias="X-Device-Timestamp"),
    db: Session = Depends(get_db),
):
    raw_body = await request.body()
    device = _device_from_token(db, device_id, x_device_token)

    # Optional HMAC verification
    if settings.DEVICE_REQUIRE_SIGNATURE:
        ok = verify_device_hmac(
            secret=device.api_token,
            timestamp=x_device_timestamp,
            signature=x_device_signature,
            body=raw_body,
        )
        if not ok:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid signature")

    # Parse the body now that auth has passed
    try:
        payload = DeviceBatchIn.model_validate_json(raw_body)
    except Exception:  # noqa: BLE001
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid payload")

    accepted = 0
    skipped = 0
    for event in payload.events:
        user = db.query(User).filter(User.biometric_id == event.biometric_id).first()
        if not user:
            skipped += 1
            continue
        ts = event.timestamp or datetime.now(timezone.utc)
        if event.event == "check_in":
            log = AttendanceLog(
                user_id=user.id,
                check_in_at=ts,
                source="biometric",
                device_id=device.id,
                latitude=event.latitude,
                longitude=event.longitude,
                status="present",
            )
            db.add(log)
            accepted += 1
        elif event.event == "check_out":
            existing = (
                db.query(AttendanceLog)
                .filter(AttendanceLog.user_id == user.id)
                .filter(AttendanceLog.check_out_at.is_(None))
                .order_by(AttendanceLog.check_in_at.desc())
                .first()
            )
            if existing:
                existing.check_out_at = ts
                accepted += 1
            else:
                skipped += 1
        else:
            skipped += 1

    device.status = "online"
    device.last_sync_at = datetime.now(timezone.utc)
    log_activity(
        db,
        actor=None,
        action="device_sync",
        resource_type="device",
        resource_id=device.id,
        request=request,
        details={"accepted": accepted, "skipped": skipped, "signed": settings.DEVICE_REQUIRE_SIGNATURE},
    )
    db.commit()
    return {"accepted": accepted, "skipped": skipped, "device_status": device.status}


@router.get("/{device_id}/health")
def device_health(
    device_id: int,
    x_device_token: str | None = Header(default=None, alias="X-Device-Token"),
    db: Session = Depends(get_db),
):
    device = _device_from_token(db, device_id, x_device_token)
    return {
        "id": device.id,
        "name": device.name,
        "status": device.status,
        "last_sync_at": device.last_sync_at,
    }
