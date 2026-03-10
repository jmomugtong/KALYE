"""Celery task for BLIP-2 image captioning inference."""

from __future__ import annotations

import logging
from pathlib import Path

from celery.exceptions import SoftTimeLimitExceeded

from src.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="captioning.run_blip",
    bind=True,
    max_retries=3,
    soft_time_limit=120,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
)
def run_captioning(self, image_id: str, image_path: str) -> str:
    """Run BLIP-2 image captioning on a street image.

    Args:
        image_id: Unique identifier for the image record.
        image_path: Filesystem path to the image file.

    Returns:
        Generated caption string describing the scene.
    """
    from src.ai.captioning.blip_captioner import BLIPCaptioner

    logger.info("Starting captioning for image %s at %s", image_id, image_path)

    self.update_state(
        state="PROGRESS",
        meta={"progress": 0, "step": "loading_model", "image_id": image_id},
    )

    try:
        captioner = BLIPCaptioner()

        self.update_state(
            state="PROGRESS",
            meta={"progress": 30, "step": "running_inference", "image_id": image_id},
        )

        caption = captioner.generate_caption(Path(image_path))

        logger.info(
            "Captioning complete for image %s: %s",
            image_id,
            caption[:100],
        )

        self.update_state(
            state="PROGRESS",
            meta={"progress": 100, "step": "completed", "image_id": image_id},
        )

        return caption

    except SoftTimeLimitExceeded:
        logger.error("Captioning task timed out for image %s", image_id)
        raise
    except FileNotFoundError:
        logger.error("Image file not found: %s", image_path)
        raise
    except Exception as exc:
        logger.error(
            "Captioning failed for image %s: %s", image_id, exc, exc_info=True
        )
        raise
