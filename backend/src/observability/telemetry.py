"""OpenTelemetry tracing setup for the KALYE platform."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Dict, Generator, Optional

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource


_tracer: Optional[trace.Tracer] = None


def setup_telemetry(
    service_name: str = "kalye-api",
    otlp_endpoint: Optional[str] = None,
) -> trace.Tracer:
    """Initialise the OpenTelemetry TracerProvider and return a tracer.

    Parameters
    ----------
    service_name:
        Logical service name attached to every span.
    otlp_endpoint:
        OTLP collector gRPC endpoint.  Falls back to the
        ``OTEL_EXPORTER_OTLP_ENDPOINT`` env-var, then ``localhost:4317``.
    """
    global _tracer

    endpoint = (
        otlp_endpoint
        or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        or "localhost:4317"
    )

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer(service_name)
    return _tracer


def get_tracer() -> trace.Tracer:
    """Return the global tracer, initialising with defaults if needed."""
    global _tracer
    if _tracer is None:
        _tracer = setup_telemetry()
    return _tracer


@contextmanager
def create_span(
    name: str,
    attributes: Optional[Dict[str, Any]] = None,
) -> Generator[trace.Span, None, None]:
    """Create and yield an OpenTelemetry span as a context manager.

    Usage::

        with create_span("process_image", {"image_id": "abc123"}):
            run_detection()
    """
    tracer = get_tracer()
    with tracer.start_as_current_span(name, attributes=attributes) as span:
        yield span
