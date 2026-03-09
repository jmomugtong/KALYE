from src.workers.celery_app import celery_app


@celery_app.task(name="captioning.run_blip", bind=True, max_retries=3)
def run_captioning(self, image_id: str, image_path: str):
    """Run BLIP-2 image captioning on a street image."""
    # TODO: Phase 7 - implement BLIP-2 captioning pipeline
    raise NotImplementedError("Captioning pipeline not yet implemented")
