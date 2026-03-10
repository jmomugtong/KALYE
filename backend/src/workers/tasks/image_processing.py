"""Celery task that orchestrates detection + segmentation + captioning."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict

from src.workers.celery_app import celery_app
from src.workers.progress_tracker import ProgressTracker

logger = logging.getLogger(__name__)

# Processing status constants
STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"


@celery_app.task(
    name="image_processing.process_image",
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
)
def process_image_task(self, image_id: str, image_path: str) -> Dict[str, Any]:
    """Orchestrate the full AI inference pipeline for a single image.

    Runs detection, segmentation, and captioning sequentially and
    combines their results into a single response dict.

    Args:
        image_id: Unique identifier for the image record.
        image_path: Filesystem path to the image file.

    Returns:
        Combined results dict with keys: image_id, status, detections,
        segmentation, caption, processing_time_ms.
    """
    from src.workers.tasks.captioning import run_captioning
    from src.workers.tasks.detection import run_yolo_detection
    from src.workers.tasks.segmentation import run_segmentation

    tracker = ProgressTracker()
    start = time.perf_counter()

    tracker.update_progress(
        task_id=self.request.id or image_id,
        progress=0,
        message="Starting image processing pipeline",
        step=STATUS_PROCESSING,
    )

    result: Dict[str, Any] = {
        "image_id": image_id,
        "status": STATUS_PROCESSING,
        "detections": [],
        "segmentation": None,
        "caption": None,
        "processing_time_ms": 0.0,
        "errors": [],
    }

    # --- Detection ---
    try:
        tracker.update_progress(
            task_id=self.request.id or image_id,
            progress=10,
            message="Running object detection",
            step="detection",
        )
        detections = run_yolo_detection.apply(
            args=[image_id, image_path]
        ).get(timeout=120)
        result["detections"] = detections
    except Exception as exc:
        logger.error("Detection failed for image %s: %s", image_id, exc)
        result["errors"].append({"step": "detection", "error": str(exc)})

    # --- Segmentation ---
    try:
        tracker.update_progress(
            task_id=self.request.id or image_id,
            progress=40,
            message="Running semantic segmentation",
            step="segmentation",
        )
        segmentation = run_segmentation.apply(
            args=[image_id, image_path]
        ).get(timeout=120)
        result["segmentation"] = segmentation
    except Exception as exc:
        logger.error("Segmentation failed for image %s: %s", image_id, exc)
        result["errors"].append({"step": "segmentation", "error": str(exc)})

    # --- Captioning ---
    try:
        tracker.update_progress(
            task_id=self.request.id or image_id,
            progress=70,
            message="Running image captioning",
            step="captioning",
        )
        caption = run_captioning.apply(
            args=[image_id, image_path]
        ).get(timeout=120)
        result["caption"] = caption
    except Exception as exc:
        logger.error("Captioning failed for image %s: %s", image_id, exc)
        result["errors"].append({"step": "captioning", "error": str(exc)})

    # --- Finalize ---
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    result["processing_time_ms"] = elapsed_ms

    if result["errors"]:
        result["status"] = STATUS_FAILED
    else:
        result["status"] = STATUS_COMPLETED

    tracker.update_progress(
        task_id=self.request.id or image_id,
        progress=100,
        message=f"Pipeline {result['status']}",
        step=result["status"],
    )

    logger.info(
        "Image processing %s for %s in %.1f ms",
        result["status"],
        image_id,
        elapsed_ms,
    )

    return result
