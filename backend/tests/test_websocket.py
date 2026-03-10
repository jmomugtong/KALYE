"""Tests for the WebSocket real-time progress system."""

from __future__ import annotations

import json
from dataclasses import asdict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.websocket.manager import MAX_CONNECTIONS, WebSocketManager
from src.api.websocket.messages import (
    CaptioningProgress,
    DetectionProgress,
    ProcessingComplete,
    ProcessingFailed,
    ProcessingStarted,
    SegmentationProgress,
    create_message,
)
from src.workers.websocket_notifier import CHANNEL_PREFIX, WebSocketNotifier


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_manager():
    """Ensure each test gets a fresh WebSocketManager singleton."""
    WebSocketManager.reset()
    yield
    WebSocketManager.reset()


def _make_ws() -> AsyncMock:
    """Create a mock WebSocket with the methods we use."""
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.send_text = AsyncMock()
    ws.close = AsyncMock()
    return ws


# ═══════════════════════════════════════════════════════════════════════════
# WebSocketManager tests
# ═══════════════════════════════════════════════════════════════════════════


class TestWebSocketManagerConnect:
    @pytest.mark.asyncio
    async def test_connect_accepts_and_tracks(self):
        manager = WebSocketManager()
        ws = _make_ws()

        result = await manager.connect(ws, "img-1", "user-1")

        assert result is True
        ws.accept.assert_awaited_once()
        assert manager.get_connection_count() == 1
        assert "img-1" in manager.active_connections
        assert ws in manager.active_connections["img-1"]

    @pytest.mark.asyncio
    async def test_connect_multiple_to_same_room(self):
        manager = WebSocketManager()
        ws1 = _make_ws()
        ws2 = _make_ws()

        await manager.connect(ws1, "img-1", "user-1")
        await manager.connect(ws2, "img-1", "user-2")

        assert manager.get_connection_count() == 2
        assert len(manager.active_connections["img-1"]) == 2

    @pytest.mark.asyncio
    async def test_connect_different_rooms(self):
        manager = WebSocketManager()
        ws1 = _make_ws()
        ws2 = _make_ws()

        await manager.connect(ws1, "img-1", "user-1")
        await manager.connect(ws2, "img-2", "user-2")

        assert manager.get_connection_count() == 2
        assert len(manager.active_connections["img-1"]) == 1
        assert len(manager.active_connections["img-2"]) == 1


class TestWebSocketManagerDisconnect:
    @pytest.mark.asyncio
    async def test_disconnect_removes_from_room(self):
        manager = WebSocketManager()
        ws = _make_ws()
        await manager.connect(ws, "img-1", "user-1")

        await manager.disconnect(ws)

        assert manager.get_connection_count() == 0
        assert "img-1" not in manager.active_connections

    @pytest.mark.asyncio
    async def test_disconnect_cleans_up_empty_room(self):
        manager = WebSocketManager()
        ws1 = _make_ws()
        ws2 = _make_ws()
        await manager.connect(ws1, "img-1", "user-1")
        await manager.connect(ws2, "img-1", "user-2")

        await manager.disconnect(ws1)

        assert manager.get_connection_count() == 1
        assert len(manager.active_connections["img-1"]) == 1

        await manager.disconnect(ws2)

        assert manager.get_connection_count() == 0
        assert "img-1" not in manager.active_connections

    @pytest.mark.asyncio
    async def test_disconnect_unknown_websocket_is_noop(self):
        manager = WebSocketManager()
        ws = _make_ws()

        # Should not raise
        await manager.disconnect(ws)
        assert manager.get_connection_count() == 0


class TestWebSocketManagerMaxConnections:
    @pytest.mark.asyncio
    async def test_rejects_when_limit_reached(self):
        manager = WebSocketManager()
        websockets = []

        # Fill to the limit
        for i in range(MAX_CONNECTIONS):
            ws = _make_ws()
            websockets.append(ws)
            result = await manager.connect(ws, f"img-{i}", f"user-{i}")
            assert result is True

        assert manager.get_connection_count() == MAX_CONNECTIONS

        # Next connection should be rejected
        ws_over_limit = _make_ws()
        result = await manager.connect(ws_over_limit, "img-extra", "user-extra")

        assert result is False
        ws_over_limit.accept.assert_not_awaited()
        assert manager.get_connection_count() == MAX_CONNECTIONS


class TestWebSocketManagerBroadcast:
    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all_in_room(self):
        manager = WebSocketManager()
        ws1 = _make_ws()
        ws2 = _make_ws()
        ws_other = _make_ws()

        await manager.connect(ws1, "img-1", "user-1")
        await manager.connect(ws2, "img-1", "user-2")
        await manager.connect(ws_other, "img-2", "user-3")

        message = {"type": "test", "data": "hello"}
        await manager.broadcast_to_room("img-1", message)

        expected_payload = json.dumps(message)
        ws1.send_text.assert_awaited_once_with(expected_payload)
        ws2.send_text.assert_awaited_once_with(expected_payload)
        ws_other.send_text.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_broadcast_to_empty_room_is_noop(self):
        manager = WebSocketManager()
        # Should not raise
        await manager.broadcast_to_room("nonexistent", {"type": "test"})

    @pytest.mark.asyncio
    async def test_broadcast_removes_dead_connections(self):
        manager = WebSocketManager()
        ws_alive = _make_ws()
        ws_dead = _make_ws()
        ws_dead.send_text.side_effect = RuntimeError("connection closed")

        await manager.connect(ws_alive, "img-1", "user-1")
        await manager.connect(ws_dead, "img-1", "user-2")

        await manager.broadcast_to_room("img-1", {"type": "test"})

        # Dead connection should have been removed
        assert manager.get_connection_count() == 1
        assert ws_alive in manager.active_connections["img-1"]


class TestWebSocketManagerPersonalMessage:
    @pytest.mark.asyncio
    async def test_send_personal_message(self):
        manager = WebSocketManager()
        ws = _make_ws()
        await manager.connect(ws, "img-1", "user-1")

        message = {"type": "hello", "to": "you"}
        await manager.send_personal_message(message, ws)

        ws.send_text.assert_awaited_once_with(json.dumps(message))

    @pytest.mark.asyncio
    async def test_personal_message_disconnects_dead_ws(self):
        manager = WebSocketManager()
        ws = _make_ws()
        ws.send_text.side_effect = RuntimeError("gone")
        await manager.connect(ws, "img-1", "user-1")

        await manager.send_personal_message({"type": "x"}, ws)

        assert manager.get_connection_count() == 0


class TestWebSocketManagerSingleton:
    def test_singleton_returns_same_instance(self):
        m1 = WebSocketManager()
        m2 = WebSocketManager()
        assert m1 is m2

    def test_reset_creates_new_instance(self):
        m1 = WebSocketManager()
        WebSocketManager.reset()
        m2 = WebSocketManager()
        assert m1 is not m2


# ═══════════════════════════════════════════════════════════════════════════
# Message creation tests
# ═══════════════════════════════════════════════════════════════════════════


class TestMessages:
    def test_processing_started_fields(self):
        msg = ProcessingStarted(image_id="img-1")
        d = asdict(msg)
        assert d["type"] == "processing_started"
        assert d["image_id"] == "img-1"
        assert "timestamp" in d

    def test_detection_progress_fields(self):
        msg = DetectionProgress(
            image_id="img-1", stage="yolo", progress=50, message="Detecting..."
        )
        d = asdict(msg)
        assert d["type"] == "detection_progress"
        assert d["progress"] == 50
        assert d["stage"] == "yolo"

    def test_segmentation_progress_fields(self):
        msg = SegmentationProgress(
            image_id="img-1", stage="segformer", progress=75, message="Segmenting..."
        )
        d = asdict(msg)
        assert d["type"] == "segmentation_progress"

    def test_captioning_progress_fields(self):
        msg = CaptioningProgress(
            image_id="img-1", stage="blip", progress=90, message="Captioning..."
        )
        d = asdict(msg)
        assert d["type"] == "captioning_progress"

    def test_processing_complete_fields(self):
        summary = {"detections": 5, "score": 72.5}
        msg = ProcessingComplete(image_id="img-1", results_summary=summary)
        d = asdict(msg)
        assert d["type"] == "processing_complete"
        assert d["results_summary"] == summary

    def test_processing_failed_fields(self):
        msg = ProcessingFailed(image_id="img-1", error="Model OOM")
        d = asdict(msg)
        assert d["type"] == "processing_failed"
        assert d["error"] == "Model OOM"


class TestCreateMessage:
    def test_create_processing_started(self):
        msg = create_message("processing_started", image_id="img-1")
        assert msg["type"] == "processing_started"
        assert msg["image_id"] == "img-1"

    def test_create_detection_progress(self):
        msg = create_message(
            "detection_progress",
            image_id="img-1",
            stage="yolo",
            progress=40,
            message="Running YOLOv8",
        )
        assert msg["type"] == "detection_progress"
        assert msg["progress"] == 40

    def test_create_processing_complete(self):
        msg = create_message(
            "processing_complete",
            image_id="img-1",
            results_summary={"count": 3},
        )
        assert msg["type"] == "processing_complete"
        assert msg["results_summary"] == {"count": 3}

    def test_create_processing_failed(self):
        msg = create_message(
            "processing_failed", image_id="img-1", error="timeout"
        )
        assert msg["type"] == "processing_failed"

    def test_create_unknown_type_raises(self):
        with pytest.raises(ValueError, match="Unknown message type"):
            create_message("nonexistent_type", image_id="img-1")

    def test_message_is_json_serializable(self):
        msg = create_message(
            "detection_progress",
            image_id="img-1",
            stage="yolo",
            progress=50,
            message="halfway",
        )
        # Should not raise
        serialized = json.dumps(msg)
        deserialized = json.loads(serialized)
        assert deserialized["type"] == "detection_progress"


# ═══════════════════════════════════════════════════════════════════════════
# WebSocketNotifier tests
# ═══════════════════════════════════════════════════════════════════════════


class TestWebSocketNotifier:
    def test_notify_progress_publishes_detection(self):
        mock_redis = MagicMock()
        notifier = WebSocketNotifier(redis_client=mock_redis)

        notifier.notify_progress("img-1", "detection", 50, "Detecting potholes")

        mock_redis.publish.assert_called_once()
        channel, payload = mock_redis.publish.call_args[0]
        assert channel == f"{CHANNEL_PREFIX}img-1"
        data = json.loads(payload)
        assert data["type"] == "detection_progress"
        assert data["image_id"] == "img-1"
        assert data["progress"] == 50
        assert data["message"] == "Detecting potholes"
        assert data["stage"] == "detection"

    def test_notify_progress_publishes_segmentation(self):
        mock_redis = MagicMock()
        notifier = WebSocketNotifier(redis_client=mock_redis)

        notifier.notify_progress("img-1", "segmentation", 70, "Segmenting sidewalks")

        channel, payload = mock_redis.publish.call_args[0]
        data = json.loads(payload)
        assert data["type"] == "segmentation_progress"

    def test_notify_progress_publishes_captioning(self):
        mock_redis = MagicMock()
        notifier = WebSocketNotifier(redis_client=mock_redis)

        notifier.notify_progress("img-1", "captioning", 90, "Generating captions")

        channel, payload = mock_redis.publish.call_args[0]
        data = json.loads(payload)
        assert data["type"] == "captioning_progress"

    def test_notify_complete(self):
        mock_redis = MagicMock()
        notifier = WebSocketNotifier(redis_client=mock_redis)
        summary = {"detections": 3, "walkability_score": 65.0}

        notifier.notify_complete("img-1", summary)

        channel, payload = mock_redis.publish.call_args[0]
        assert channel == f"{CHANNEL_PREFIX}img-1"
        data = json.loads(payload)
        assert data["type"] == "processing_complete"
        assert data["results_summary"] == summary

    def test_notify_failed(self):
        mock_redis = MagicMock()
        notifier = WebSocketNotifier(redis_client=mock_redis)

        notifier.notify_failed("img-1", "GPU out of memory")

        channel, payload = mock_redis.publish.call_args[0]
        data = json.loads(payload)
        assert data["type"] == "processing_failed"
        assert data["error"] == "GPU out of memory"

    def test_notify_progress_handles_redis_error(self):
        mock_redis = MagicMock()
        mock_redis.publish.side_effect = ConnectionError("Redis down")
        notifier = WebSocketNotifier(redis_client=mock_redis)

        # Should not raise
        notifier.notify_progress("img-1", "detection", 50, "test")

    def test_notify_complete_handles_redis_error(self):
        mock_redis = MagicMock()
        mock_redis.publish.side_effect = ConnectionError("Redis down")
        notifier = WebSocketNotifier(redis_client=mock_redis)

        # Should not raise
        notifier.notify_complete("img-1", {})

    def test_notify_failed_handles_redis_error(self):
        mock_redis = MagicMock()
        mock_redis.publish.side_effect = ConnectionError("Redis down")
        notifier = WebSocketNotifier(redis_client=mock_redis)

        # Should not raise
        notifier.notify_failed("img-1", "error")

    def test_message_contains_timestamp(self):
        mock_redis = MagicMock()
        notifier = WebSocketNotifier(redis_client=mock_redis)

        notifier.notify_progress("img-1", "detection", 10, "starting")

        _, payload = mock_redis.publish.call_args[0]
        data = json.loads(payload)
        assert "timestamp" in data

    def test_unknown_stage_defaults_to_detection(self):
        mock_redis = MagicMock()
        notifier = WebSocketNotifier(redis_client=mock_redis)

        notifier.notify_progress("img-1", "unknown_stage", 10, "test")

        _, payload = mock_redis.publish.call_args[0]
        data = json.loads(payload)
        assert data["type"] == "detection_progress"


class TestWebSocketNotifierLazyRedis:
    @patch("src.config.settings.get_settings")
    def test_lazy_redis_connection(self, mock_get_settings):
        mock_settings = MagicMock()
        mock_settings.redis_url = "redis://localhost:6379/0"
        mock_get_settings.return_value = mock_settings

        mock_redis_cls = MagicMock()
        with patch.dict("sys.modules", {"redis": mock_redis_cls}):
            # Need a fresh notifier so the lazy property fires
            notifier = WebSocketNotifier()
            _ = notifier.redis

            mock_redis_cls.Redis.from_url.assert_called_once_with(
                "redis://localhost:6379/0", decode_responses=True
            )
