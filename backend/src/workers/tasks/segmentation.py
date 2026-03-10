"""Celery task for SegFormer semantic segmentation inference."""

from __future__ import annotations

import logging
from dataclasses import asdict
from pathlib import Path

from celery.exceptions import SoftTimeLimitExceeded

from src.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="segmentation.run_segformer",
    bind=True,
    max_retries=3,
    soft_time_limit=120,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
)
def run_segmentation(self, image_id: str, image_path: str) -> dict:
    """Run SegFormer semantic segmentation on a street image.

    Args:
        image_id: Unique identifier for the image record.
        image_path: Filesystem path to the image file.

    Returns:
        Segmentation result dict with keys: mask, class_labels,
        class_counts, sidewalk_coverage, inference_time_ms.
    """
    from src.ai.segmentation.segformer import SegFormerSegmenter

    logger.info("Starting segmentation for image %s at %s", image_id, image_path)

    self.update_state(
        state="PROGRESS",
        meta={"progress": 0, "step": "loading_model", "image_id": image_id},
    )

    try:
        segmenter = SegFormerSegmenter()

        self.update_state(
            state="PROGRESS",
            meta={"progress": 30, "step": "running_inference", "image_id": image_id},
        )

        result = segmenter.segment(Path(image_path))

        self.update_state(
            state="PROGRESS",
            meta={"progress": 90, "step": "postprocessing", "image_id": image_id},
        )

        result_dict = asdict(result)

        logger.info(
            "Segmentation complete for image %s: sidewalk_coverage=%.2f%%",
            image_id,
            result.sidewalk_coverage * 100,
        )

        self.update_state(
            state="PROGRESS",
            meta={"progress": 100, "step": "completed", "image_id": image_id},
        )

        return result_dict

    except SoftTimeLimitExceeded:
        logger.error("Segmentation task timed out for image %s", image_id)
        raise
    except FileNotFoundError:
        logger.error("Image file not found: %s", image_path)
        raise
    except Exception as exc:
        logger.error(
            "Segmentation failed for image %s: %s", image_id, exc, exc_info=True
        )
        raise
