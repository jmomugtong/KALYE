#!/usr/bin/env python3
"""Performance benchmark suite for KALYE infrastructure.

Measures dummy inference timing, database query latency, and storage I/O.

Usage:
    python performance_benchmark.py
    python performance_benchmark.py --iterations 50 --output report.json
"""

import argparse
import json
import os
import statistics
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class BenchmarkStats:
    name: str
    iterations: int
    mean_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    min_ms: float
    max_ms: float
    error: str | None = None


def _percentile(data: list[float], pct: float) -> float:
    """Calculate the given percentile from a sorted list."""
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * (pct / 100.0)
    f = int(k)
    c = f + 1
    if c >= len(sorted_data):
        return sorted_data[f]
    return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])


def _compute_stats(name: str, timings_ms: list[float]) -> BenchmarkStats:
    return BenchmarkStats(
        name=name,
        iterations=len(timings_ms),
        mean_ms=round(statistics.mean(timings_ms), 3),
        p50_ms=round(_percentile(timings_ms, 50), 3),
        p95_ms=round(_percentile(timings_ms, 95), 3),
        p99_ms=round(_percentile(timings_ms, 99), 3),
        min_ms=round(min(timings_ms), 3),
        max_ms=round(max(timings_ms), 3),
    )


# ---------------------------------------------------------------------------
# Benchmark functions
# ---------------------------------------------------------------------------


def bench_dummy_inference(iterations: int) -> BenchmarkStats:
    """Simulate an inference pass with matrix operations."""
    try:
        import numpy as np
    except ImportError:
        return BenchmarkStats(
            name="dummy_inference", iterations=0,
            mean_ms=0, p50_ms=0, p95_ms=0, p99_ms=0, min_ms=0, max_ms=0,
            error="numpy not installed",
        )

    timings: list[float] = []
    for _ in range(iterations):
        # Simulate a small forward pass: random matmul + ReLU
        a = np.random.randn(256, 256).astype(np.float32)
        b = np.random.randn(256, 256).astype(np.float32)
        start = time.perf_counter()
        c = a @ b
        c = np.maximum(c, 0)  # ReLU
        _ = c.sum()
        elapsed = (time.perf_counter() - start) * 1000
        timings.append(elapsed)

    return _compute_stats("dummy_inference", timings)


def bench_db_query(iterations: int) -> BenchmarkStats:
    """Measure round-trip latency for a simple SELECT 1 query."""
    db_url = os.environ.get(
        "DATABASE_URL_SYNC",
        os.environ.get("DATABASE_URL", "postgresql://kalye:kalye_dev@localhost:5432/kalye"),
    )
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

    try:
        from sqlalchemy import create_engine, text

        engine = create_engine(db_url, pool_pre_ping=True)
    except Exception as e:
        return BenchmarkStats(
            name="db_query", iterations=0,
            mean_ms=0, p50_ms=0, p95_ms=0, p99_ms=0, min_ms=0, max_ms=0,
            error=str(e),
        )

    timings: list[float] = []
    try:
        with engine.connect() as conn:
            for _ in range(iterations):
                start = time.perf_counter()
                conn.execute(text("SELECT 1"))
                elapsed = (time.perf_counter() - start) * 1000
                timings.append(elapsed)
        engine.dispose()
    except Exception as e:
        return BenchmarkStats(
            name="db_query", iterations=0,
            mean_ms=0, p50_ms=0, p95_ms=0, p99_ms=0, min_ms=0, max_ms=0,
            error=str(e),
        )

    return _compute_stats("db_query", timings)


def bench_storage_io(iterations: int) -> BenchmarkStats:
    """Measure local disk write + read latency (1 KB payload)."""
    payload = os.urandom(1024)  # 1 KB
    timings: list[float] = []

    with tempfile.TemporaryDirectory(prefix="kalye_bench_") as tmpdir:
        filepath = Path(tmpdir) / "bench_file.bin"
        for _ in range(iterations):
            start = time.perf_counter()
            filepath.write_bytes(payload)
            _ = filepath.read_bytes()
            elapsed = (time.perf_counter() - start) * 1000
            timings.append(elapsed)
            filepath.unlink(missing_ok=True)

    return _compute_stats("storage_io", timings)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

BENCHMARKS = [
    ("Dummy Inference (256x256 matmul + ReLU)", bench_dummy_inference),
    ("Database Query (SELECT 1)", bench_db_query),
    ("Storage I/O (1KB write+read)", bench_storage_io),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="KALYE performance benchmark suite.")
    parser.add_argument(
        "--iterations", "-n", type=int, default=10,
        help="Number of iterations per benchmark (default: 10).",
    )
    parser.add_argument(
        "--output", "-o", type=str, default=None,
        help="Path to write JSON report.",
    )
    args = parser.parse_args()

    print(f"\nKALYE Performance Benchmark — {args.iterations} iterations each\n")
    print("-" * 70)

    results: list[dict] = []
    for label, func in BENCHMARKS:
        print(f"\n  Running: {label} ...")
        stats = func(args.iterations)
        results.append(asdict(stats))

        if stats.error:
            print(f"    ERROR: {stats.error}")
        else:
            print(f"    Mean:  {stats.mean_ms:.3f} ms")
            print(f"    P50:   {stats.p50_ms:.3f} ms")
            print(f"    P95:   {stats.p95_ms:.3f} ms")
            print(f"    P99:   {stats.p99_ms:.3f} ms")
            print(f"    Range: [{stats.min_ms:.3f}, {stats.max_ms:.3f}] ms")

    print("\n" + "-" * 70)

    report = {
        "benchmark": "kalye-performance",
        "iterations": args.iterations,
        "results": results,
    }

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2))
        print(f"\nReport written to: {output_path.resolve()}")
    else:
        print("\nTip: use --output report.json to save the full report.")

    print()


if __name__ == "__main__":
    main()
