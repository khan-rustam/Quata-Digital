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

from app.core.security import decode_token
from app.db.session import SessionLocal
from app.models import User

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


@router.websocket("/ws/messages")
async def messages_ws(websocket: WebSocket, token: str = Query(default="")):
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
            # We mostly push to the client. Allow the client to send ping/typing.
            data = await websocket.receive_text()
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
