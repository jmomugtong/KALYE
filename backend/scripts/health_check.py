#!/usr/bin/env python3
"""Health-check script for KALYE infrastructure services.

Checks PostgreSQL, Redis, MinIO, and Ollama. Exits 0 if all pass, 1 otherwise.

Usage:
    python health_check.py
    python health_check.py --verbose
"""

import argparse
import os
import sys
import time
from dataclasses import dataclass, field

# ANSI color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"


@dataclass
class CheckResult:
    name: str
    ok: bool
    message: str
    elapsed_ms: float = 0.0
    details: dict = field(default_factory=dict)


def _format_status(result: CheckResult, verbose: bool) -> str:
    icon = f"{GREEN}OK{RESET}" if result.ok else f"{RED}FAIL{RESET}"
    line = f"  [{icon}] {result.name}: {result.message}"
    if verbose:
        line += f"  ({result.elapsed_ms:.1f}ms)"
        if result.details:
            for k, v in result.details.items():
                line += f"\n        {k}: {v}"
    return line


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def check_postgres(verbose: bool) -> CheckResult:
    """Check PostgreSQL connectivity with SELECT 1."""
    db_url = os.environ.get(
        "DATABASE_URL_SYNC",
        os.environ.get("DATABASE_URL", "postgresql://kalye:kalye_dev@localhost:5432/kalye"),
    )
    # Ensure sync driver
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

    start = time.perf_counter()
    try:
        from sqlalchemy import create_engine, text

        engine = create_engine(db_url, pool_pre_ping=True)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            val = result.scalar()
        engine.dispose()
        elapsed = (time.perf_counter() - start) * 1000

        details = {"url": db_url.split("@")[-1]} if verbose else {}
        if val == 1:
            return CheckResult("PostgreSQL", True, "connected", elapsed, details)
        return CheckResult("PostgreSQL", False, f"unexpected result: {val}", elapsed, details)
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        return CheckResult("PostgreSQL", False, str(e), elapsed)


def check_redis(verbose: bool) -> CheckResult:
    """Check Redis with PING."""
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    start = time.perf_counter()
    try:
        import redis

        r = redis.from_url(redis_url, socket_connect_timeout=3)
        pong = r.ping()
        r.close()
        elapsed = (time.perf_counter() - start) * 1000

        details = {"url": redis_url} if verbose else {}
        if pong:
            return CheckResult("Redis", True, "PONG", elapsed, details)
        return CheckResult("Redis", False, "no PONG response", elapsed, details)
    except ImportError:
        return CheckResult("Redis", False, "redis package not installed", 0)
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        return CheckResult("Redis", False, str(e), elapsed)


def check_minio(verbose: bool) -> CheckResult:
    """Check MinIO by listing buckets."""
    endpoint = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
    access_key = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
    secret_key = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
    secure = os.environ.get("MINIO_SECURE", "false").lower() == "true"

    start = time.perf_counter()
    try:
        from minio import Minio

        client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)
        buckets = client.list_buckets()
        elapsed = (time.perf_counter() - start) * 1000

        bucket_names = [b.name for b in buckets]
        details = {"endpoint": endpoint, "buckets": bucket_names} if verbose else {}
        return CheckResult(
            "MinIO",
            True,
            f"{len(buckets)} bucket(s) found",
            elapsed,
            details,
        )
    except ImportError:
        return CheckResult("MinIO", False, "minio package not installed", 0)
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        return CheckResult("MinIO", False, str(e), elapsed)


def check_ollama(verbose: bool) -> CheckResult:
    """Check Ollama LLM server via /api/tags."""
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    url = f"{base_url}/api/tags"

    start = time.perf_counter()
    try:
        import urllib.request
        import json

        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        elapsed = (time.perf_counter() - start) * 1000

        models = [m.get("name", "?") for m in data.get("models", [])]
        details = {"url": base_url, "models": models} if verbose else {}
        return CheckResult(
            "Ollama",
            True,
            f"{len(models)} model(s) available",
            elapsed,
            details,
        )
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        return CheckResult("Ollama", False, str(e), elapsed)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="KALYE infrastructure health check.")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show connection details and timings."
    )
    args = parser.parse_args()

    print(f"\n{BOLD}KALYE Health Check{RESET}\n")

    checks = [
        check_postgres(args.verbose),
        check_redis(args.verbose),
        check_minio(args.verbose),
        check_ollama(args.verbose),
    ]

    for result in checks:
        print(_format_status(result, args.verbose))

    passed = sum(1 for c in checks if c.ok)
    total = len(checks)

    color = GREEN if passed == total else (YELLOW if passed > 0 else RED)
    print(f"\n{color}{passed}/{total} services healthy{RESET}\n")

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
