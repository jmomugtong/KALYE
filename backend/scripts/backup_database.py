#!/usr/bin/env python3
"""Backup the KALYE PostgreSQL database using pg_dump.

Creates a gzip-compressed SQL dump with a timestamped filename.
Retains the most recent 7 backups and deletes older ones.

Usage:
    python backup_database.py
    python backup_database.py --output-dir ./backups
    python backup_database.py --dry-run
"""

import argparse
import gzip
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


def parse_db_url(url: str) -> dict:
    """Extract host, port, database, user, and password from a PostgreSQL URL."""
    # Strip driver suffixes like +asyncpg
    clean = url.split("://", 1)
    if len(clean) == 2:
        scheme_base = clean[0].split("+")[0]
        url = f"{scheme_base}://{clean[1]}"

    parsed = urlparse(url)
    return {
        "host": parsed.hostname or "localhost",
        "port": str(parsed.port or 5432),
        "database": (parsed.path or "/kalye").lstrip("/"),
        "user": parsed.username or "kalye",
        "password": parsed.password or "",
    }


def find_pg_dump() -> str | None:
    """Find pg_dump executable on the system."""
    return shutil.which("pg_dump")


def run_backup(db_info: dict, output_path: Path, dry_run: bool) -> bool:
    """Execute pg_dump and compress the output with gzip."""
    pg_dump = find_pg_dump()
    if not pg_dump:
        print("ERROR: pg_dump not found on PATH.", file=sys.stderr)
        print("       Install PostgreSQL client tools and try again.", file=sys.stderr)
        return False

    raw_path = output_path.with_suffix("")  # remove .gz for pg_dump target
    cmd = [
        pg_dump,
        "-h", db_info["host"],
        "-p", db_info["port"],
        "-U", db_info["user"],
        "-d", db_info["database"],
        "--no-owner",
        "--no-acl",
        "-f", str(raw_path),
    ]

    if dry_run:
        print(f"  [DRY-RUN] Would run: {' '.join(cmd)}")
        print(f"  [DRY-RUN] Would compress to: {output_path}")
        return True

    env = os.environ.copy()
    if db_info["password"]:
        env["PGPASSWORD"] = db_info["password"]

    print(f"  Running pg_dump → {raw_path.name} ...")
    try:
        result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            print(f"  ERROR: pg_dump failed: {result.stderr.strip()}", file=sys.stderr)
            return False
    except FileNotFoundError:
        print("  ERROR: pg_dump executable not found.", file=sys.stderr)
        return False
    except subprocess.TimeoutExpired:
        print("  ERROR: pg_dump timed out after 5 minutes.", file=sys.stderr)
        return False

    # Compress with gzip
    print(f"  Compressing → {output_path.name} ...")
    try:
        with open(raw_path, "rb") as f_in:
            with gzip.open(output_path, "wb", compresslevel=6) as f_out:
                shutil.copyfileobj(f_in, f_out)
        raw_path.unlink()  # remove uncompressed file
    except Exception as e:
        print(f"  ERROR: compression failed: {e}", file=sys.stderr)
        return False

    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"  Backup complete: {output_path.name} ({size_mb:.2f} MB)")
    return True


def enforce_retention(output_dir: Path, keep: int, dry_run: bool) -> int:
    """Delete old backups, keeping only the most recent `keep` files."""
    backups = sorted(
        output_dir.glob("kalye_backup_*.sql.gz"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    to_delete = backups[keep:]
    for old_backup in to_delete:
        if dry_run:
            print(f"  [DRY-RUN] Would delete: {old_backup.name}")
        else:
            old_backup.unlink()
            print(f"  [DELETED] {old_backup.name}")

    return len(to_delete)


def main() -> None:
    default_url = os.environ.get(
        "DATABASE_URL_SYNC",
        os.environ.get("DATABASE_URL", "postgresql://kalye:kalye_dev@localhost:5432/kalye"),
    )

    parser = argparse.ArgumentParser(description="Backup the KALYE PostgreSQL database.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./backups"),
        help="Directory to store backup files (default: ./backups).",
    )
    parser.add_argument(
        "--database-url",
        default=default_url,
        help="PostgreSQL connection URL (default from DATABASE_URL_SYNC env).",
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=7,
        help="Number of recent backups to retain (default: 7).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without creating or deleting files.",
    )

    args = parser.parse_args()

    db_info = parse_db_url(args.database_url)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"kalye_backup_{timestamp}.sql.gz"

    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.output_dir / filename

    print(f"\nKALYE Database Backup")
    print(f"  Database: {db_info['database']}@{db_info['host']}:{db_info['port']}")
    print(f"  Output:   {output_path}")
    print(f"  Dry run:  {args.dry_run}\n")

    success = run_backup(db_info, output_path, args.dry_run)
    if not success and not args.dry_run:
        sys.exit(1)

    print(f"\n  Retention policy: keep last {args.keep} backups")
    deleted = enforce_retention(args.output_dir, args.keep, args.dry_run)
    if deleted:
        print(f"  Cleaned up {deleted} old backup(s).")
    else:
        print("  No old backups to clean up.")

    print()


if __name__ == "__main__":
    main()
