#!/usr/bin/env python3
"""Generate a deployment-readiness launch checklist for KALYE.

Runs automated checks for key files, Docker build readiness, and environment
variable validation. Produces a JSON report and prints a summary.

Usage:
    python scripts/generate_launch_checklist.py
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

# Project root is two levels up if run from scripts/, or CWD otherwise
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent


@dataclass
class CheckItem:
    category: str
    name: str
    passed: bool
    message: str


# ---------------------------------------------------------------------------
# Check functions
# ---------------------------------------------------------------------------

REQUIRED_FILES = [
    "README.md",
    "CONTRIBUTING.md",
    "CLAUDE.md",
    ".env.example",
    "docker-compose.yml",
    "Makefile",
    "backend/pyproject.toml",
    "backend/src/db/models.py",
    "backend/src/db/postgres.py",
    "backend/alembic.ini",
    "backend/scripts/health_check.py",
    "backend/scripts/seed_database.py",
    "backend/scripts/download_models.py",
    "backend/scripts/backup_database.py",
    "backend/scripts/performance_benchmark.py",
]

REQUIRED_DIRECTORIES = [
    "backend/src",
    "backend/tests",
    "backend/alembic",
    "frontend",
    "infrastructure",
    "docs",
    "models",
    "data",
    "scripts",
]

REQUIRED_ENV_VARS = [
    "DATABASE_URL",
    "REDIS_URL",
    "MINIO_ENDPOINT",
    "MINIO_ACCESS_KEY",
    "MINIO_SECRET_KEY",
    "JWT_SECRET_KEY",
    "NEXTAUTH_SECRET",
]

ENV_EXAMPLE_VARS = [
    "DATABASE_URL",
    "REDIS_URL",
    "MINIO_ENDPOINT",
    "MINIO_ACCESS_KEY",
    "MINIO_SECRET_KEY",
    "S3_BUCKET_NAME",
    "JWT_SECRET_KEY",
    "JWT_ALGORITHM",
    "MAPBOX_ACCESS_TOKEN",
    "OLLAMA_BASE_URL",
]


def check_required_files() -> list[CheckItem]:
    """Verify that all required project files exist."""
    results = []
    for rel_path in REQUIRED_FILES:
        full_path = PROJECT_ROOT / rel_path
        exists = full_path.exists()
        results.append(CheckItem(
            category="files",
            name=rel_path,
            passed=exists,
            message="found" if exists else "MISSING",
        ))
    return results


def check_required_directories() -> list[CheckItem]:
    """Verify that all required directories exist."""
    results = []
    for rel_path in REQUIRED_DIRECTORIES:
        full_path = PROJECT_ROOT / rel_path
        exists = full_path.is_dir()
        results.append(CheckItem(
            category="directories",
            name=rel_path,
            passed=exists,
            message="found" if exists else "MISSING",
        ))
    return results


def check_env_example() -> list[CheckItem]:
    """Verify .env.example contains all required variable definitions."""
    results = []
    env_file = PROJECT_ROOT / ".env.example"
    if not env_file.exists():
        results.append(CheckItem(
            category="env_example",
            name=".env.example",
            passed=False,
            message="file not found",
        ))
        return results

    content = env_file.read_text()
    for var in ENV_EXAMPLE_VARS:
        found = f"{var}=" in content
        results.append(CheckItem(
            category="env_example",
            name=var,
            passed=found,
            message="defined" if found else "MISSING from .env.example",
        ))
    return results


def check_env_vars_set() -> list[CheckItem]:
    """Check whether required environment variables are set (informational)."""
    results = []
    for var in REQUIRED_ENV_VARS:
        is_set = var in os.environ and len(os.environ[var]) > 0
        results.append(CheckItem(
            category="env_runtime",
            name=var,
            passed=is_set,
            message="set" if is_set else "NOT SET (may be OK in dev)",
        ))
    return results


def check_docker_compose() -> list[CheckItem]:
    """Validate docker-compose.yml syntax (dry run)."""
    results = []
    compose_file = PROJECT_ROOT / "docker-compose.yml"

    if not compose_file.exists():
        results.append(CheckItem(
            category="docker",
            name="docker-compose.yml",
            passed=False,
            message="file not found",
        ))
        return results

    docker_compose_cmd = None
    if shutil.which("docker"):
        docker_compose_cmd = ["docker", "compose", "config", "--quiet"]
    elif shutil.which("docker-compose"):
        docker_compose_cmd = ["docker-compose", "config", "--quiet"]

    if docker_compose_cmd is None:
        results.append(CheckItem(
            category="docker",
            name="docker CLI",
            passed=False,
            message="docker not found on PATH",
        ))
        return results

    try:
        proc = subprocess.run(
            docker_compose_cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        valid = proc.returncode == 0
        msg = "valid syntax" if valid else f"invalid: {proc.stderr.strip()[:120]}"
        results.append(CheckItem(
            category="docker",
            name="docker-compose.yml syntax",
            passed=valid,
            message=msg,
        ))
    except subprocess.TimeoutExpired:
        results.append(CheckItem(
            category="docker",
            name="docker-compose.yml syntax",
            passed=False,
            message="validation timed out",
        ))
    except Exception as e:
        results.append(CheckItem(
            category="docker",
            name="docker-compose.yml syntax",
            passed=False,
            message=str(e),
        ))

    return results


def check_tools_available() -> list[CheckItem]:
    """Check that key CLI tools are available."""
    tools = {
        "python3": ["python3", "--version"],
        "node": ["node", "--version"],
        "docker": ["docker", "--version"],
        "git": ["git", "--version"],
    }
    results = []
    for name, cmd in tools.items():
        found = shutil.which(cmd[0]) is not None
        version = ""
        if found:
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                version = proc.stdout.strip().split("\n")[0]
            except Exception:
                version = "unknown version"
        results.append(CheckItem(
            category="tools",
            name=name,
            passed=found,
            message=version if found else "NOT FOUND",
        ))
    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a KALYE deployment-readiness launch checklist.",
    )
    parser.add_argument(
        "--output", "-o", type=str, default=None,
        help="Path to write JSON report (default: print to stdout).",
    )
    args = parser.parse_args()

    all_checks: list[CheckItem] = []
    all_checks.extend(check_required_files())
    all_checks.extend(check_required_directories())
    all_checks.extend(check_env_example())
    all_checks.extend(check_env_vars_set())
    all_checks.extend(check_docker_compose())
    all_checks.extend(check_tools_available())

    # Build report
    passed = sum(1 for c in all_checks if c.passed)
    total = len(all_checks)
    score = round((passed / total) * 100, 1) if total > 0 else 0.0

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "project_root": str(PROJECT_ROOT),
        "total_checks": total,
        "passed": passed,
        "failed": total - passed,
        "readiness_score": score,
        "checks": [asdict(c) for c in all_checks],
    }

    # Print summary
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

    print(f"\n{BOLD}KALYE Launch Checklist{RESET}\n")

    current_category = None
    for c in all_checks:
        if c.category != current_category:
            current_category = c.category
            print(f"\n  {BOLD}[{current_category.upper()}]{RESET}")
        icon = f"{GREEN}PASS{RESET}" if c.passed else f"{RED}FAIL{RESET}"
        print(f"    [{icon}] {c.name}: {c.message}")

    color = GREEN if score >= 90 else (YELLOW if score >= 70 else RED)
    print(f"\n{BOLD}Deployment Readiness Score: {color}{score}%{RESET}")
    print(f"  {passed}/{total} checks passed\n")

    # Write JSON report
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2))
        print(f"Report written to: {output_path.resolve()}\n")
    else:
        # Also dump JSON to stdout for piping
        print(json.dumps(report, indent=2))

    sys.exit(0 if score >= 70 else 1)


if __name__ == "__main__":
    main()
