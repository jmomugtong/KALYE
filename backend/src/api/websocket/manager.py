"""WebSocket connection manager with room-based messaging."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from fastapi import WebSocket

logger = logging.getLogger(__name__)

MAX_CONNECTIONS = 100


class WebSocketManager:
    """Singleton manager that tracks WebSocket connections grouped by room.

    Each room corresponds to an ``image_id`` so that all clients watching the
    same image processing pipeline receive the same progress updates.
    """

    _instance: WebSocketManager | None = None

    def __new__(cls) -> WebSocketManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.active_connections: Dict[str, List[WebSocket]] = {}
            cls._instance._ws_to_room: Dict[int, str] = {}
        return cls._instance

    # ── Connection lifecycle ────────────────────────────────────────────

    async def connect(
        self,
        websocket: WebSocket,
        image_id: str,
        user_id: str,
    ) -> bool:
        """Accept *websocket* and add it to the room for *image_id*.

        Returns ``False`` if the global connection limit has been reached.
        """
        if self.get_connection_count() >= MAX_CONNECTIONS:
            logger.warning(
                "Connection limit reached (%d). Rejecting user %s for image %s.",
                MAX_CONNECTIONS,
                user_id,
                image_id,
            )
            return False

        await websocket.accept()

        room_id = image_id
        if room_id not in self.active_connections:
            self.active_connections[room_id] = []
        self.active_connections[room_id].append(websocket)
        self._ws_to_room[id(websocket)] = room_id

        logger.info(
            "User %s connected to room %s (total connections: %d)",
            user_id,
            room_id,
            self.get_connection_count(),
        )
        return True

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove *websocket* from its room and clean up empty rooms."""
        room_id = self._ws_to_room.pop(id(websocket), None)
        if room_id is None:
            return

        conns = self.active_connections.get(room_id, [])
        if websocket in conns:
            conns.remove(websocket)
        if not conns:
            self.active_connections.pop(room_id, None)

        logger.info(
            "WebSocket disconnected from room %s (total connections: %d)",
            room_id,
            self.get_connection_count(),
        )

    # ── Messaging ───────────────────────────────────────────────────────

    async def broadcast_to_room(self, room_id: str, message: dict) -> None:
        """Send *message* to every connection in *room_id*."""
        payload = json.dumps(message)
        dead: List[WebSocket] = []

        for ws in self.active_connections.get(room_id, []):
            try:
                await ws.send_text(payload)
            except Exception:
                logger.warning("Failed to send to ws in room %s; marking for removal", room_id)
                dead.append(ws)

        for ws in dead:
            await self.disconnect(ws)

    async def send_personal_message(self, message: dict, websocket: WebSocket) -> None:
        """Send *message* to a single *websocket*."""
        try:
            await websocket.send_text(json.dumps(message))
        except Exception:
            logger.warning("Failed to send personal message")
            await self.disconnect(websocket)

    # ── Introspection ───────────────────────────────────────────────────

    def get_connection_count(self) -> int:
        """Return the total number of active connections across all rooms."""
        return sum(len(conns) for conns in self.active_connections.values())

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton — useful for tests."""
        cls._instance = None
