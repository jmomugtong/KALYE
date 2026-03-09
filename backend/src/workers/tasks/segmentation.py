from src.workers.celery_app import celery_app


@celery_app.task(name="segmentation.run_segformer", bind=True, max_retries=3)
def run_segmentation(self, image_id: str, image_path: str):
    """Run SegFormer semantic segmentation on a street image."""
    # TODO: Phase 6 - implement SegFormer inference pipeline
    raise NotImplementedError("Segmentation pipeline not yet implemented")
