"""Celery task for batch image processing using Celery groups."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List

from celery import group

from src.workers.celery_app import celery_app
from src.workers.tasks.image_processing import process_image_task

logger = logging.getLogger(__name__)


@celery_app.task(
    name="batch_processing.process_batch",
    bind=True,
    max_retries=3,
)
def process_batch_task(
    self, image_ids: List[str], image_paths: List[str] | None = None
) -> Dict[str, Any]:
    """Process multiple images in parallel using a Celery group.

    Args:
        image_ids: List of image identifiers to process.
        image_paths: Optional list of filesystem paths, one per image_id.
            When not provided, each image_id is used as the path (useful
            when IDs *are* paths).

    Returns:
        Batch summary dict with keys: total, completed, failed,
        results, processing_time_ms.
    """
    if image_paths is None:
        image_paths = image_ids

    if len(image_ids) != len(image_paths):
        raise ValueError(
            f"image_ids ({len(image_ids)}) and image_paths ({len(image_paths)}) "
            "must have the same length"
        )

    logger.info("Starting batch processing for %d images", len(image_ids))
    start = time.perf_counter()

    self.update_state(
        state="PROGRESS",
        meta={
            "progress": 0,
            "step": "dispatching",
            "total": len(image_ids),
        },
    )

    # Build a group of process_image tasks
    job = group(
        process_image_task.s(img_id, img_path)
        for img_id, img_path in zip(image_ids, image_paths)
    )

    group_result = job.apply_async()

    self.update_state(
        state="PROGRESS",
        meta={
            "progress": 10,
            "step": "processing",
            "total": len(image_ids),
        },
    )

    # Wait for all tasks to complete (with a generous timeout)
    timeout_per_image = 180  # seconds
    total_timeout = timeout_per_image * len(image_ids)
    try:
        results = group_result.get(timeout=total_timeout, propagate=False)
    except Exception as exc:
        logger.error("Batch processing failed: %s", exc)
        results = []

    elapsed_ms = (time.perf_counter() - start) * 1000.0

    completed = sum(
        1 for r in results if isinstance(r, dict) and r.get("status") == "completed"
    )
    failed = sum(
        1 for r in results if isinstance(r, dict) and r.get("status") == "failed"
    )
    errored = len(image_ids) - completed - failed

    summary: Dict[str, Any] = {
        "total": len(image_ids),
        "completed": completed,
        "failed": failed + errored,
        "results": results,
        "processing_time_ms": elapsed_ms,
    }

    self.update_state(
        state="PROGRESS",
        meta={"progress": 100, "step": "completed", "total": len(image_ids)},
    )

    logger.info(
        "Batch complete: %d/%d succeeded in %.1f ms",
        completed,
        len(image_ids),
        elapsed_ms,
    )

    return summary
