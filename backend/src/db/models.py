import enum
import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ─── Enums ────────────────────────────────────────────────────────────────────


class UserRole(str, enum.Enum):
    admin = "admin"
    lgu_user = "lgu_user"
    public = "public"


class ProcessingStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class DetectionType(str, enum.Enum):
    pothole = "pothole"
    sidewalk_obstruction = "sidewalk_obstruction"
    missing_sign = "missing_sign"
    curb_ramp = "curb_ramp"
    broken_sidewalk = "broken_sidewalk"
    flooding = "flooding"
    missing_ramp = "missing_ramp"


class FeedbackType(str, enum.Enum):
    correct = "correct"
    incorrect = "incorrect"
    missing_detection = "missing_detection"


# ─── Models ───────────────────────────────────────────────────────────────────


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"), default=UserRole.public, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    images: Mapped[list["Image"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    feedbacks: Mapped[list["UserFeedback"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Image(Base):
    __tablename__ = "images"

    image_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(50), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    location = mapped_column(Geometry("POINT", srid=4326), nullable=True)
    image_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus, name="processing_status"),
        default=ProcessingStatus.pending,
        nullable=False,
        index=True,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="images")
    detections: Mapped[list["Detection"]] = relationship(
        back_populates="image", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_images_user_id", "user_id"),
        Index("idx_images_location", "location", postgresql_using="gist"),
    )


class Detection(Base):
    __tablename__ = "detections"

    detection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    image_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("images.image_id", ondelete="CASCADE"), nullable=False
    )
    detection_type: Mapped[DetectionType] = mapped_column(
        Enum(DetectionType, name="detection_type"), nullable=False, index=True
    )
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    bounding_box: Mapped[dict] = mapped_column(JSONB, nullable=False)
    location = mapped_column(Geometry("POINT", srid=4326), nullable=True)
    detection_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    embedding = mapped_column(Vector(384), nullable=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    image: Mapped["Image"] = relationship(back_populates="detections")
    feedbacks: Mapped[list["UserFeedback"]] = relationship(
        back_populates="detection", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_detections_image_id", "image_id"),
        Index("idx_detections_location", "location", postgresql_using="gist"),
    )


class Location(Base):
    __tablename__ = "locations"

    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    barangay_name: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(255), nullable=False)
    geometry = mapped_column(Geometry("POLYGON", srid=4326), nullable=True)
    population: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    walkability_scores: Mapped[list["WalkabilityScore"]] = relationship(
        back_populates="location", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_locations_geometry", "geometry", postgresql_using="gist"),
        Index("idx_locations_city_barangay", "city", "barangay_name"),
    )


class WalkabilityScore(Base):
    __tablename__ = "walkability_scores"

    score_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.location_id", ondelete="CASCADE"), nullable=False
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    breakdown: Mapped[dict] = mapped_column(JSONB, nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    version: Mapped[str] = mapped_column(String(50), nullable=False, default="1.0")

    location: Mapped["Location"] = relationship(back_populates="walkability_scores")

    __table_args__ = (Index("idx_walkability_location_id", "location_id"),)


class UserFeedback(Base):
    __tablename__ = "user_feedbacks"

    feedback_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    detection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("detections.detection_id", ondelete="SET NULL"),
        nullable=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    feedback_type: Mapped[FeedbackType] = mapped_column(
        Enum(FeedbackType, name="feedback_type"), nullable=False
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    detection: Mapped["Detection | None"] = relationship(back_populates="feedbacks")
    user: Mapped["User"] = relationship(back_populates="feedbacks")
