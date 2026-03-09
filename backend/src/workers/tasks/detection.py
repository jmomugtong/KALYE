from src.workers.celery_app import celery_app


@celery_app.task(name="detection.run_yolo", bind=True, max_retries=3)
def run_yolo_detection(self, image_id: str, image_path: str):
    """Run YOLOv8 object detection on a street image."""
    # TODO: Phase 5 - implement YOLOv8 inference pipeline
    raise NotImplementedError("Detection pipeline not yet implemented")
