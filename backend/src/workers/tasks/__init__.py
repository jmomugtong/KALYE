"""Celery task modules for the KALYE inference pipeline."""

from src.workers.tasks.batch_processing import process_batch_task
from src.workers.tasks.captioning import run_captioning
from src.workers.tasks.detection import run_yolo_detection
from src.workers.tasks.image_processing import process_image_task
from src.workers.tasks.segmentation import run_segmentation

__all__ = [
    "run_yolo_detection",
    "run_segmentation",
    "run_captioning",
    "process_image_task",
    "process_batch_task",
]
