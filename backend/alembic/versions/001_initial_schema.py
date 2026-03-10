"""Initial schema with PostGIS and pgvector

Revision ID: 001
Revises:
Create Date: 2026-03-09

"""
from typing import Sequence, Union

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create enum types
    user_role = postgresql.ENUM("admin", "lgu_user", "public", name="user_role", create_type=False)
    user_role.create(op.get_bind(), checkfirst=True)

    processing_status = postgresql.ENUM(
        "pending", "processing", "completed", "failed",
        name="processing_status", create_type=False,
    )
    processing_status.create(op.get_bind(), checkfirst=True)

    detection_type = postgresql.ENUM(
        "pothole", "sidewalk_obstruction", "missing_sign", "curb_ramp",
        "broken_sidewalk", "flooding", "missing_ramp",
        name="detection_type", create_type=False,
    )
    detection_type.create(op.get_bind(), checkfirst=True)

    feedback_type = postgresql.ENUM(
        "correct", "incorrect", "missing_detection",
        name="feedback_type", create_type=False,
    )
    feedback_type.create(op.get_bind(), checkfirst=True)

    # Users
    op.create_table(
        "users",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", user_role, nullable=False, server_default="public"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # Images
    op.create_table(
        "images",
        sa.Column("image_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("storage_path", sa.String(512), nullable=False),
        sa.Column("file_size_bytes", sa.Integer, nullable=False),
        sa.Column("mime_type", sa.String(50), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("location", geoalchemy2.Geometry("POINT", srid=4326), nullable=True),
        sa.Column("image_metadata", postgresql.JSONB, nullable=True),
        sa.Column("processing_status", processing_status, nullable=False, server_default="pending"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_images_user_id", "images", ["user_id"])
    op.create_index("idx_images_location", "images", ["location"], postgresql_using="gist")
    op.create_index("idx_images_processing_status", "images", ["processing_status"])

    # Detections
    op.create_table(
        "detections",
        sa.Column("detection_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("image_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("images.image_id", ondelete="CASCADE"), nullable=False),
        sa.Column("detection_type", detection_type, nullable=False),
        sa.Column("confidence_score", sa.Float, nullable=False),
        sa.Column("bounding_box", postgresql.JSONB, nullable=False),
        sa.Column("location", geoalchemy2.Geometry("POINT", srid=4326), nullable=True),
        sa.Column("detection_metadata", postgresql.JSONB, nullable=True),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column("caption", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_detections_image_id", "detections", ["image_id"])
    op.create_index("idx_detections_detection_type", "detections", ["detection_type"])
    op.create_index("idx_detections_location", "detections", ["location"], postgresql_using="gist")

    # Locations (barangay boundaries)
    op.create_table(
        "locations",
        sa.Column("location_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("barangay_name", sa.String(255), nullable=False),
        sa.Column("city", sa.String(255), nullable=False),
        sa.Column("geometry", geoalchemy2.Geometry("POLYGON", srid=4326), nullable=True),
        sa.Column("population", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_locations_geometry", "locations", ["geometry"], postgresql_using="gist")
    op.create_index("idx_locations_city_barangay", "locations", ["city", "barangay_name"])

    # Walkability Scores
    op.create_table(
        "walkability_scores",
        sa.Column("score_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("locations.location_id", ondelete="CASCADE"), nullable=False),
        sa.Column("score", sa.Integer, nullable=False),
        sa.Column("breakdown", postgresql.JSONB, nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("version", sa.String(50), nullable=False, server_default="1.0"),
    )
    op.create_index("idx_walkability_location_id", "walkability_scores", ["location_id"])

    # User Feedbacks
    op.create_table(
        "user_feedbacks",
        sa.Column("feedback_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("detection_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("detections.detection_id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("feedback_type", feedback_type, nullable=False),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("user_feedbacks")
    op.drop_table("walkability_scores")
    op.drop_table("locations")
    op.drop_table("detections")
    op.drop_table("images")
    op.drop_table("users")

    op.execute("DROP TYPE IF EXISTS feedback_type")
    op.execute("DROP TYPE IF EXISTS detection_type")
    op.execute("DROP TYPE IF EXISTS processing_status")
    op.execute("DROP TYPE IF EXISTS user_role")
    op.execute("DROP EXTENSION IF EXISTS vector")
    op.execute("DROP EXTENSION IF EXISTS postgis")
