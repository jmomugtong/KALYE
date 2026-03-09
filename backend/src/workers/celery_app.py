from celery import Celery

from src.config.settings import get_settings

settings = get_settings()

celery_app = Celery(
    "kalye",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Manila",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "src.workers.tasks.detection.*": {"queue": "detection"},
        "src.workers.tasks.segmentation.*": {"queue": "segmentation"},
        "src.workers.tasks.captioning.*": {"queue": "captioning"},
    },
)

celery_app.autodiscover_tasks(["src.workers.tasks"])
