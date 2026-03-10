"""WebSocket message types for real-time processing progress."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Message dataclasses ─────────────────────────────────────────────────────


@dataclass
class ProcessingStarted:
    image_id: str
    timestamp: str = field(default_factory=_now_iso)
    type: str = field(default="processing_started", init=False)


@dataclass
class DetectionProgress:
    image_id: str
    stage: str
    progress: int
    message: str
    timestamp: str = field(default_factory=_now_iso)
    type: str = field(default="detection_progress", init=False)


@dataclass
class SegmentationProgress:
    image_id: str
    stage: str
    progress: int
    message: str
    timestamp: str = field(default_factory=_now_iso)
    type: str = field(default="segmentation_progress", init=False)


@dataclass
class CaptioningProgress:
    image_id: str
    stage: str
    progress: int
    message: str
    timestamp: str = field(default_factory=_now_iso)
    type: str = field(default="captioning_progress", init=False)


@dataclass
class ProcessingComplete:
    image_id: str
    results_summary: Dict[str, Any]
    timestamp: str = field(default_factory=_now_iso)
    type: str = field(default="processing_complete", init=False)


@dataclass
class ProcessingFailed:
    image_id: str
    error: str
    timestamp: str = field(default_factory=_now_iso)
    type: str = field(default="processing_failed", init=False)


# ── Message type registry ───────────────────────────────────────────────────

_MESSAGE_TYPES: Dict[str, type] = {
    "processing_started": ProcessingStarted,
    "detection_progress": DetectionProgress,
    "segmentation_progress": SegmentationProgress,
    "captioning_progress": CaptioningProgress,
    "processing_complete": ProcessingComplete,
    "processing_failed": ProcessingFailed,
}


def create_message(msg_type: str, **kwargs: Any) -> dict:
    """Factory that builds a message dict for the given *msg_type*.

    Args:
        msg_type: One of the registered message type names.
        **kwargs: Fields forwarded to the dataclass constructor.

    Returns:
        A plain dict ready for JSON serialisation.

    Raises:
        ValueError: If *msg_type* is not recognised.
    """
    cls = _MESSAGE_TYPES.get(msg_type)
    if cls is None:
        raise ValueError(
            f"Unknown message type '{msg_type}'. "
            f"Valid types: {', '.join(_MESSAGE_TYPES)}"
        )
    return asdict(cls(**kwargs))
