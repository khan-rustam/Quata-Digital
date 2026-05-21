"""WebSocket endpoint for real-time staff messaging.

Authentication: pass the JWT in the `?token=` query param (browsers can't set
custom WebSocket headers).
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Dict, Set

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_token
from app.db.session import SessionLocal
from app.models import User

# Cap inbound WebSocket frames to a sensible ceiling so a misbehaving client
# can't pin a worker on a multi-megabyte text frame. We only accept ping
# heartbeats from the browser side; everything else is server-pushed.
_MAX_WS_MESSAGE_BYTES = 4 * 1024

router = APIRouter(tags=["ws"])
log = logging.getLogger("quata.ws")


class Hub:
    """In-process pub/sub. For multi-process deployments use Redis pub/sub or
    Postgres LISTEN/NOTIFY. The interface is the same."""

    def __init__(self) -> None:
        # user_id -> set of connections
        self.subscribers: Dict[int, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, user_id: int, ws: WebSocket) -> None:
        async with self._lock:
            self.subscribers.setdefault(user_id, set()).add(ws)

    async def disconnect(self, user_id: int, ws: WebSocket) -> None:
        async with self._lock:
            conns = self.subscribers.get(user_id)
            if conns:
                conns.discard(ws)
                if not conns:
                    self.subscribers.pop(user_id, None)

    async def broadcast(self, to_user_ids: set[int] | list[int], event: dict) -> None:
        msg = json.dumps(event, default=str)
        async with self._lock:
            targets = []
            for uid in set(to_user_ids):
                for conn in self.subscribers.get(uid, set()):
                    targets.append(conn)
        for conn in targets:
            try:
                await conn.send_text(msg)
            except Exception:  # noqa: BLE001
                pass


hub = Hub()


def _user_from_token(token: str | None) -> User | None:
    if not token:
        return None
    sub = decode_token(token)
    if not sub:
        return None
    db: Session = SessionLocal()
    try:
        return db.get(User, int(sub))
    finally:
        db.close()


def _origin_allowed(origin: str | None) -> bool:
    """Cross-origin WebSocket guard.

    Browsers do not enforce the same-origin policy on the WS handshake,
    so we must do it ourselves — otherwise a malicious page could spawn
    authenticated sockets in a victim's browser if the token leaks via
    URL referer/log/etc. ``None`` is allowed for native clients (mobile,
    curl) that don't send Origin; auth is still enforced by the token.
    """
    if not origin:
        return True
    return origin in set(settings.cors_origins)


@router.websocket("/ws/messages")
async def messages_ws(websocket: WebSocket, token: str = Query(default="")):
    if not _origin_allowed(websocket.headers.get("origin")):
        await websocket.close(code=4403)
        return
    user = _user_from_token(token)
    if not user or not user.is_active:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    await hub.connect(user.id, websocket)
    log.info("ws.connect", extra={"user_id": user.id})

    # Initial hello
    await websocket.send_json({
        "type": "hello",
        "user_id": user.id,
        "full_name": user.full_name,
    })

    try:
        while True:
            # Server is the primary writer here; the client only sends
            # ping/typing heartbeats. Cap inbound frames so a runaway
            # client can't OOM a worker on a single multi-MB text frame.
            data = await websocket.receive_text()
            if len(data) > _MAX_WS_MESSAGE_BYTES:
                await websocket.close(code=1009)  # message too big
                return
            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                continue
            if payload.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        await hub.disconnect(user.id, websocket)
        log.info("ws.disconnect", extra={"user_id": user.id})
