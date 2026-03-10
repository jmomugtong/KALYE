"""Tests for the KALYE observability module."""

import time

import pytest
from prometheus_client import CollectorRegistry, Counter, Histogram, Gauge, REGISTRY
from starlette.testclient import TestClient
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route


# ---------------------------------------------------------------------------
# Fixtures – isolated registry so tests don't leak into each other
# ---------------------------------------------------------------------------

@pytest.fixture()
def registry():
    """Return a fresh CollectorRegistry for test isolation."""
    return CollectorRegistry()


@pytest.fixture()
def counter(registry):
    return Counter(
        "test_counter_total",
        "A test counter",
        labelnames=["label_a"],
        registry=registry,
    )


@pytest.fixture()
def histogram(registry):
    return Histogram(
        "test_histogram_seconds",
        "A test histogram",
        buckets=(0.1, 0.5, 1.0),
        registry=registry,
    )


@pytest.fixture()
def gauge(registry):
    return Gauge(
        "test_gauge_value",
        "A test gauge",
        registry=registry,
    )


# ---------------------------------------------------------------------------
# Counter tests
# ---------------------------------------------------------------------------

class TestCounter:
    def test_increment(self, counter, registry):
        counter.labels(label_a="x").inc()
        counter.labels(label_a="x").inc()
        assert registry.get_sample_value(
            "test_counter_total", {"label_a": "x"}
        ) == 2.0

    def test_increment_different_labels(self, counter, registry):
        counter.labels(label_a="a").inc()
        counter.labels(label_a="b").inc(3)
        assert registry.get_sample_value(
            "test_counter_total", {"label_a": "a"}
        ) == 1.0
        assert registry.get_sample_value(
            "test_counter_total", {"label_a": "b"}
        ) == 3.0


# ---------------------------------------------------------------------------
# Histogram tests
# ---------------------------------------------------------------------------

class TestHistogram:
    def test_observe(self, histogram, registry):
        histogram.observe(0.25)
        histogram.observe(0.75)
        assert registry.get_sample_value("test_histogram_seconds_count") == 2.0
        assert registry.get_sample_value("test_histogram_seconds_sum") == pytest.approx(1.0)

    def test_bucket_boundaries(self, histogram, registry):
        histogram.observe(0.05)  # fits in 0.1 bucket
        assert registry.get_sample_value(
            "test_histogram_seconds_bucket", {"le": "0.1"}
        ) == 1.0
        assert registry.get_sample_value(
            "test_histogram_seconds_bucket", {"le": "0.5"}
        ) == 1.0


# ---------------------------------------------------------------------------
# Gauge tests
# ---------------------------------------------------------------------------

class TestGauge:
    def test_set(self, gauge, registry):
        gauge.set(42)
        assert registry.get_sample_value("test_gauge_value") == 42.0

    def test_inc_dec(self, gauge, registry):
        gauge.set(10)
        gauge.inc(5)
        assert registry.get_sample_value("test_gauge_value") == 15.0
        gauge.dec(3)
        assert registry.get_sample_value("test_gauge_value") == 12.0


# ---------------------------------------------------------------------------
# Middleware tests
# ---------------------------------------------------------------------------

class TestPrometheusMiddleware:
    @pytest.fixture(autouse=True)
    def _reset_metrics(self):
        """Clear the default-registry metrics used by the middleware between tests."""
        from backend.src.observability.metrics import (
            kalye_api_requests_total,
            kalye_api_latency_seconds,
        )
        # We cannot unregister default-registry collectors easily, but we can
        # read the values before/after and assert on the delta.
        yield

    @staticmethod
    def _build_app():
        from backend.src.observability.middleware import PrometheusMiddleware

        async def homepage(request):
            return PlainTextResponse("ok")

        async def health(request):
            return PlainTextResponse("healthy")

        async def metrics(request):
            return PlainTextResponse("metrics")

        app = Starlette(
            routes=[
                Route("/", homepage),
                Route("/health", health),
                Route("/metrics", metrics),
                Route("/api/test", homepage),
            ],
        )
        app.add_middleware(PrometheusMiddleware)
        return app

    def test_middleware_records_request(self):
        from backend.src.observability.metrics import kalye_api_requests_total

        app = self._build_app()
        client = TestClient(app)

        # Capture value before request
        before = REGISTRY.get_sample_value(
            "kalye_api_requests_total",
            {"endpoint": "/api/test", "method": "GET", "status_code": "200"},
        ) or 0.0

        client.get("/api/test")

        after = REGISTRY.get_sample_value(
            "kalye_api_requests_total",
            {"endpoint": "/api/test", "method": "GET", "status_code": "200"},
        ) or 0.0

        assert after - before == 1.0

    def test_middleware_skips_health(self):
        from backend.src.observability.metrics import kalye_api_requests_total

        app = self._build_app()
        client = TestClient(app)

        before = REGISTRY.get_sample_value(
            "kalye_api_requests_total",
            {"endpoint": "/health", "method": "GET", "status_code": "200"},
        ) or 0.0

        client.get("/health")

        after = REGISTRY.get_sample_value(
            "kalye_api_requests_total",
            {"endpoint": "/health", "method": "GET", "status_code": "200"},
        ) or 0.0

        assert after - before == 0.0

    def test_middleware_skips_metrics(self):
        app = self._build_app()
        client = TestClient(app)

        before = REGISTRY.get_sample_value(
            "kalye_api_requests_total",
            {"endpoint": "/metrics", "method": "GET", "status_code": "200"},
        ) or 0.0

        client.get("/metrics")

        after = REGISTRY.get_sample_value(
            "kalye_api_requests_total",
            {"endpoint": "/metrics", "method": "GET", "status_code": "200"},
        ) or 0.0

        assert after - before == 0.0

    def test_middleware_records_latency(self):
        app = self._build_app()
        client = TestClient(app)

        before_count = REGISTRY.get_sample_value(
            "kalye_api_latency_seconds_count"
        ) or 0.0

        client.get("/api/test")

        after_count = REGISTRY.get_sample_value(
            "kalye_api_latency_seconds_count"
        ) or 0.0

        assert after_count - before_count == 1.0


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------

class TestRecordRequest:
    def test_record_request_increments_counter(self):
        from backend.src.observability.metrics import (
            record_request,
            kalye_api_requests_total,
        )

        before = REGISTRY.get_sample_value(
            "kalye_api_requests_total",
            {"endpoint": "/helper-test", "method": "POST", "status_code": "201"},
        ) or 0.0

        record_request("/helper-test", "POST", 201)

        after = REGISTRY.get_sample_value(
            "kalye_api_requests_total",
            {"endpoint": "/helper-test", "method": "POST", "status_code": "201"},
        ) or 0.0

        assert after - before == 1.0


class TestRecordDetection:
    def test_record_detection_high_confidence(self):
        from backend.src.observability.metrics import (
            record_detection,
            kalye_detections_total,
        )

        before = REGISTRY.get_sample_value(
            "kalye_detections_total",
            {"detection_type": "pothole", "confidence_bucket": "0.9-1.0"},
        ) or 0.0

        record_detection("pothole", 0.95)

        after = REGISTRY.get_sample_value(
            "kalye_detections_total",
            {"detection_type": "pothole", "confidence_bucket": "0.9-1.0"},
        ) or 0.0

        assert after - before == 1.0

    def test_record_detection_medium_confidence(self):
        from backend.src.observability.metrics import record_detection

        before = REGISTRY.get_sample_value(
            "kalye_detections_total",
            {"detection_type": "barrier", "confidence_bucket": "0.7-0.9"},
        ) or 0.0

        record_detection("barrier", 0.75)

        after = REGISTRY.get_sample_value(
            "kalye_detections_total",
            {"detection_type": "barrier", "confidence_bucket": "0.7-0.9"},
        ) or 0.0

        assert after - before == 1.0

    def test_record_detection_low_confidence(self):
        from backend.src.observability.metrics import record_detection

        before = REGISTRY.get_sample_value(
            "kalye_detections_total",
            {"detection_type": "sign", "confidence_bucket": "0.0-0.5"},
        ) or 0.0

        record_detection("sign", 0.3)

        after = REGISTRY.get_sample_value(
            "kalye_detections_total",
            {"detection_type": "sign", "confidence_bucket": "0.0-0.5"},
        ) or 0.0

        assert after - before == 1.0


class TestObserveLatency:
    def test_observe_latency_context_manager(self):
        from backend.src.observability.metrics import (
            observe_latency,
            kalye_detection_duration_seconds,
        )

        before_count = REGISTRY.get_sample_value(
            "kalye_detection_duration_seconds_count"
        ) or 0.0

        with observe_latency(kalye_detection_duration_seconds):
            time.sleep(0.01)

        after_count = REGISTRY.get_sample_value(
            "kalye_detection_duration_seconds_count"
        ) or 0.0

        assert after_count - before_count == 1.0
