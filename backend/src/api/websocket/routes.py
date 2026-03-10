"""WebSocket route for real-time image processing progress."""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from src.api.middleware.auth import verify_token
from src.api.websocket.manager import WebSocketManager
from src.api.websocket.messages import create_message

logger = logging.getLogger(__name__)

router = APIRouter()

HEARTBEAT_INTERVAL_SECONDS = 30


@router.websocket("/ws/processing/{image_id}")
async def processing_progress(
    websocket: WebSocket,
    image_id: str,
    token: str = Query(...),
) -> None:
    """WebSocket endpoint streaming processing progress for *image_id*.

    Authentication is performed via the ``token`` query parameter which must
    contain a valid JWT.  A heartbeat ping is sent every 30 seconds to keep
    the connection alive.
    """
    # ── Auth ────────────────────────────────────────────────────────────
    try:
        payload = verify_token(token)
        user_id: str = payload.get("sub", "anonymous")
    except Exception:
        await websocket.close(code=4001, reason="Invalid or missing token")
        return

    # ── Connect ─────────────────────────────────────────────────────────
    manager = WebSocketManager()
    connected = await manager.connect(websocket, image_id, user_id)
    if not connected:
        await websocket.close(code=4002, reason="Connection limit reached")
        return

    # Notify the client that processing tracking has started
    await manager.send_personal_message(
        create_message("processing_started", image_id=image_id),
        websocket,
    )

    # ── Heartbeat + receive loop ────────────────────────────────────────
    try:
        while True:
            try:
                # Wait for client messages with a timeout for heartbeat
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=HEARTBEAT_INTERVAL_SECONDS,
                )
                # Clients may send pong or other messages; we just acknowledge
                if data:
                    try:
                        msg = json.loads(data)
                        if msg.get("type") == "ping":
                            await manager.send_personal_message(
                                {"type": "pong"}, websocket
                            )
                    except json.JSONDecodeError:
                        pass
            except asyncio.TimeoutError:
                # Send heartbeat ping to keep the connection alive
                try:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                except Exception:
                    break
    except WebSocketDisconnect:
        logger.info("Client disconnected from image %s", image_id)
    except Exception:
        logger.exception("Unexpected error in WebSocket for image %s", image_id)
    finally:
        await manager.disconnect(websocket)
