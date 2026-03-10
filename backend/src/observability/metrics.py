"""Prometheus metrics definitions and helper functions for the KALYE platform."""

from contextlib import contextmanager
import time
from typing import Optional

from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, REGISTRY


# ---------------------------------------------------------------------------
# Counters
# ---------------------------------------------------------------------------

kalye_api_requests_total = Counter(
    "kalye_api_requests_total",
    "Total API requests",
    labelnames=["endpoint", "method", "status_code"],
)

kalye_image_uploads_total = Counter(
    "kalye_image_uploads_total",
    "Total image uploads",
    labelnames=["status"],
)

kalye_detections_total = Counter(
    "kalye_detections_total",
    "Total detections produced by AI models",
    labelnames=["detection_type", "confidence_bucket"],
)

kalye_celery_tasks_total = Counter(
    "kalye_celery_tasks_total",
    "Total Celery tasks executed",
    labelnames=["task_name", "status"],
)

# ---------------------------------------------------------------------------
# Histograms
# ---------------------------------------------------------------------------

kalye_detection_duration_seconds = Histogram(
    "kalye_detection_duration_seconds",
    "Duration of object detection inference",
    buckets=(0.1, 0.5, 1, 2, 5, 10),
)

kalye_segmentation_duration_seconds = Histogram(
    "kalye_segmentation_duration_seconds",
    "Duration of segmentation inference",
    buckets=(0.5, 1, 2, 3, 5),
)

kalye_api_latency_seconds = Histogram(
    "kalye_api_latency_seconds",
    "API request latency",
    buckets=(0.01, 0.05, 0.1, 0.5, 1, 2, 5),
)

kalye_db_query_duration_seconds = Histogram(
    "kalye_db_query_duration_seconds",
    "Database query duration",
    buckets=(0.01, 0.05, 0.1, 0.5, 1),
)

# ---------------------------------------------------------------------------
# Gauges
# ---------------------------------------------------------------------------

kalye_walkability_score_avg = Gauge(
    "kalye_walkability_score_avg",
    "Average walkability score per barangay",
    labelnames=["barangay"],
)

kalye_active_websocket_connections = Gauge(
    "kalye_active_websocket_connections",
    "Number of active WebSocket connections",
)

kalye_celery_queue_length = Gauge(
    "kalye_celery_queue_length",
    "Current length of the Celery task queue",
)

kalye_redis_cache_hit_rate = Gauge(
    "kalye_redis_cache_hit_rate",
    "Redis cache hit rate (0-1)",
)

kalye_storage_usage_bytes = Gauge(
    "kalye_storage_usage_bytes",
    "Total storage usage in bytes",
)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def record_request(endpoint: str, method: str, status_code: int) -> None:
    """Record an API request in the counter and optionally the histogram."""
    kalye_api_requests_total.labels(
        endpoint=endpoint,
        method=method,
        status_code=str(status_code),
    ).inc()


def record_detection(detection_type: str, confidence: float) -> None:
    """Record a detection event with a bucketed confidence label."""
    if confidence >= 0.9:
        bucket = "0.9-1.0"
    elif confidence >= 0.7:
        bucket = "0.7-0.9"
    elif confidence >= 0.5:
        bucket = "0.5-0.7"
    else:
        bucket = "0.0-0.5"

    kalye_detections_total.labels(
        detection_type=detection_type,
        confidence_bucket=bucket,
    ).inc()


def record_task(task_name: str, status: str) -> None:
    """Record a Celery task completion."""
    kalye_celery_tasks_total.labels(
        task_name=task_name,
        status=status,
    ).inc()


@contextmanager
def observe_latency(histogram: Histogram):
    """Context manager that observes the duration of a block in a histogram.

    Usage::

        with observe_latency(kalye_api_latency_seconds):
            do_work()
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        histogram.observe(elapsed)
