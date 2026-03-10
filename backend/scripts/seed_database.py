#!/usr/bin/env python3
"""Seed the KALYE database with sample barangay data and test users.

Usage:
    python seed_database.py
    python seed_database.py --database-url postgresql://user:pass@host/db
    python seed_database.py --dry-run
"""

import argparse
import os
import sys
import uuid

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

# Ensure the backend source is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.db.models import Base, Location, User, UserRole, WalkabilityScore

# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

BARANGAYS = [
    {
        "barangay_name": "Poblacion",
        "city": "Makati",
        "population": 8743,
        "geometry_wkt": (
            "SRID=4326;POLYGON(("
            "121.0310 14.5640, 121.0360 14.5640, 121.0360 14.5590, "
            "121.0310 14.5590, 121.0310 14.5640))"
        ),
    },
    {
        "barangay_name": "Ermita",
        "city": "Manila",
        "population": 7573,
        "geometry_wkt": (
            "SRID=4326;POLYGON(("
            "120.9800 14.5820, 120.9870 14.5820, 120.9870 14.5760, "
            "120.9800 14.5760, 120.9800 14.5820))"
        ),
    },
    {
        "barangay_name": "Bagumbayan",
        "city": "Taguig",
        "population": 25134,
        "geometry_wkt": (
            "SRID=4326;POLYGON(("
            "121.0500 14.5300, 121.0590 14.5300, 121.0590 14.5230, "
            "121.0500 14.5230, 121.0500 14.5300))"
        ),
    },
    {
        "barangay_name": "Wack-Wack Greenhills",
        "city": "Mandaluyong",
        "population": 6102,
        "geometry_wkt": (
            "SRID=4326;POLYGON(("
            "121.0380 14.5850, 121.0450 14.5850, 121.0450 14.5790, "
            "121.0380 14.5790, 121.0380 14.5850))"
        ),
    },
    {
        "barangay_name": "Kapitolyo",
        "city": "Pasig",
        "population": 14389,
        "geometry_wkt": (
            "SRID=4326;POLYGON(("
            "121.0560 14.5750, 121.0640 14.5750, 121.0640 14.5690, "
            "121.0560 14.5690, 121.0560 14.5750))"
        ),
    },
]

TEST_USERS = [
    {
        "email": "admin@kalye.dev",
        "hashed_password": "$2b$12$LJ3m4ys0Pp.RnP1b5sT9zuEQ7ZjCwRvGqZfK2E8D.Q1d3cXZvGMaG",
        "role": UserRole.admin,
    },
    {
        "email": "lgu@kalye.dev",
        "hashed_password": "$2b$12$LJ3m4ys0Pp.RnP1b5sT9zuEQ7ZjCwRvGqZfK2E8D.Q1d3cXZvGMaG",
        "role": UserRole.lgu_user,
    },
    {
        "email": "public@kalye.dev",
        "hashed_password": "$2b$12$LJ3m4ys0Pp.RnP1b5sT9zuEQ7ZjCwRvGqZfK2E8D.Q1d3cXZvGMaG",
        "role": UserRole.public,
    },
]

INITIAL_SCORES = [
    {"barangay": "Poblacion", "score": 72, "breakdown": {
        "sidewalk_coverage": 0.65, "obstruction_density": 0.15,
        "ada_compliance": 0.80, "lighting": 0.70,
    }},
    {"barangay": "Ermita", "score": 58, "breakdown": {
        "sidewalk_coverage": 0.50, "obstruction_density": 0.30,
        "ada_compliance": 0.55, "lighting": 0.60,
    }},
    {"barangay": "Bagumbayan", "score": 65, "breakdown": {
        "sidewalk_coverage": 0.60, "obstruction_density": 0.20,
        "ada_compliance": 0.70, "lighting": 0.55,
    }},
    {"barangay": "Wack-Wack Greenhills", "score": 78, "breakdown": {
        "sidewalk_coverage": 0.75, "obstruction_density": 0.10,
        "ada_compliance": 0.85, "lighting": 0.80,
    }},
    {"barangay": "Kapitolyo", "score": 70, "breakdown": {
        "sidewalk_coverage": 0.68, "obstruction_density": 0.18,
        "ada_compliance": 0.72, "lighting": 0.65,
    }},
]

# ---------------------------------------------------------------------------
# Seeding logic
# ---------------------------------------------------------------------------


def seed_locations(session: Session, dry_run: bool) -> int:
    """Insert barangay locations if they do not already exist."""
    created = 0
    for b in BARANGAYS:
        existing = session.execute(
            text(
                "SELECT 1 FROM locations WHERE barangay_name = :name AND city = :city"
            ),
            {"name": b["barangay_name"], "city": b["city"]},
        ).fetchone()
        if existing:
            print(f"  [SKIP] Location: {b['barangay_name']}, {b['city']}")
            continue

        if dry_run:
            print(f"  [DRY-RUN] Would create location: {b['barangay_name']}, {b['city']}")
        else:
            loc = Location(
                location_id=uuid.uuid4(),
                barangay_name=b["barangay_name"],
                city=b["city"],
                population=b["population"],
            )
            session.add(loc)
            session.flush()
            # Set geometry using raw SQL for WKT support
            session.execute(
                text(
                    "UPDATE locations SET geometry = ST_GeomFromEWKT(:wkt) "
                    "WHERE location_id = :lid"
                ),
                {"wkt": b["geometry_wkt"], "lid": str(loc.location_id)},
            )
            print(f"  [CREATED] Location: {b['barangay_name']}, {b['city']}")
        created += 1
    return created


def seed_users(session: Session, dry_run: bool) -> int:
    """Insert test users if they do not already exist."""
    created = 0
    for u in TEST_USERS:
        existing = session.execute(
            text("SELECT 1 FROM users WHERE email = :email"),
            {"email": u["email"]},
        ).fetchone()
        if existing:
            print(f"  [SKIP] User: {u['email']}")
            continue

        if dry_run:
            print(f"  [DRY-RUN] Would create user: {u['email']} ({u['role'].value})")
        else:
            user = User(
                user_id=uuid.uuid4(),
                email=u["email"],
                hashed_password=u["hashed_password"],
                role=u["role"],
            )
            session.add(user)
            print(f"  [CREATED] User: {u['email']} ({u['role'].value})")
        created += 1
    return created


def seed_walkability_scores(session: Session, dry_run: bool) -> int:
    """Insert baseline walkability scores for seeded locations."""
    created = 0
    for s in INITIAL_SCORES:
        loc_row = session.execute(
            text("SELECT location_id FROM locations WHERE barangay_name = :name"),
            {"name": s["barangay"]},
        ).fetchone()
        if not loc_row:
            print(f"  [SKIP] Score for {s['barangay']}: location not found")
            continue

        location_id = loc_row[0]
        existing = session.execute(
            text("SELECT 1 FROM walkability_scores WHERE location_id = :lid"),
            {"lid": str(location_id)},
        ).fetchone()
        if existing:
            print(f"  [SKIP] Score: {s['barangay']} (already scored)")
            continue

        if dry_run:
            print(f"  [DRY-RUN] Would create score: {s['barangay']} = {s['score']}")
        else:
            ws = WalkabilityScore(
                score_id=uuid.uuid4(),
                location_id=location_id,
                score=s["score"],
                breakdown=s["breakdown"],
                version="1.0",
            )
            session.add(ws)
            print(f"  [CREATED] Score: {s['barangay']} = {s['score']}")
        created += 1
    return created


def main() -> None:
    default_url = os.environ.get(
        "DATABASE_URL_SYNC",
        "postgresql://kalye:kalye_dev@localhost:5432/kalye",
    )

    parser = argparse.ArgumentParser(
        description="Seed the KALYE database with sample data.",
    )
    parser.add_argument(
        "--database-url",
        default=default_url,
        help=f"PostgreSQL connection string (default from DATABASE_URL_SYNC env or {default_url}).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be seeded without modifying the database.",
    )

    args = parser.parse_args()

    # Ensure we use a sync driver
    db_url = args.database_url.replace("postgresql+asyncpg://", "postgresql://")

    print(f"\nDatabase: {db_url.split('@')[-1]}")
    print(f"Dry run:  {args.dry_run}\n")

    engine = create_engine(db_url)

    with Session(engine) as session:
        print("--- Locations ---")
        loc_count = seed_locations(session, args.dry_run)

        print("\n--- Users ---")
        user_count = seed_users(session, args.dry_run)

        print("\n--- Walkability Scores ---")
        score_count = seed_walkability_scores(session, args.dry_run)

        if not args.dry_run:
            session.commit()
            print("\nCommitted to database.")

    print("\n=== Seed Summary ===")
    label = "Would create" if args.dry_run else "Created"
    print(f"  {label} {loc_count} location(s)")
    print(f"  {label} {user_count} user(s)")
    print(f"  {label} {score_count} walkability score(s)")
    print()


if __name__ == "__main__":
    main()
