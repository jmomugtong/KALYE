"""Celery task for YOLOv8 object detection inference."""

from __future__ import annotations

import logging
from dataclasses import asdict
from pathlib import Path

from celery.exceptions import SoftTimeLimitExceeded

from src.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="detection.run_yolo",
    bind=True,
    max_retries=3,
    soft_time_limit=120,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
)
def run_yolo_detection(self, image_id: str, image_path: str) -> list[dict]:
    """Run YOLOv8 object detection on a street image.

    Args:
        image_id: Unique identifier for the image record.
        image_path: Filesystem path to the image file.

    Returns:
        List of detection dicts with keys: detection_type, confidence,
        bounding_box, class_id, inference_time_ms.
    """
    from src.ai.detection.yolo_detector import YOLODetector

    logger.info("Starting YOLO detection for image %s at %s", image_id, image_path)

    self.update_state(
        state="PROGRESS",
        meta={"progress": 0, "step": "loading_model", "image_id": image_id},
    )

    try:
        detector = YOLODetector()

        self.update_state(
            state="PROGRESS",
            meta={"progress": 30, "step": "running_inference", "image_id": image_id},
        )

        results = detector.detect(Path(image_path))

        self.update_state(
            state="PROGRESS",
            meta={"progress": 90, "step": "postprocessing", "image_id": image_id},
        )

        detections = [asdict(r) for r in results]

        logger.info(
            "Detection complete for image %s: %d detections found",
            image_id,
            len(detections),
        )

        self.update_state(
            state="PROGRESS",
            meta={"progress": 100, "step": "completed", "image_id": image_id},
        )

        return detections

    except SoftTimeLimitExceeded:
        logger.error("Detection task timed out for image %s", image_id)
        raise
    except FileNotFoundError:
        logger.error("Image file not found: %s", image_path)
        raise
    except Exception as exc:
        logger.error(
            "Detection failed for image %s: %s", image_id, exc, exc_info=True
        )
        raise
