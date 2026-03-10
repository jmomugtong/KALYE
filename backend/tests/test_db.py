"""Tests for database models, schema validation, and geospatial queries.

These tests require a running PostgreSQL+PostGIS+pgvector instance.
Set DATABASE_URL env var or use docker compose up postgres.
"""

import uuid
from datetime import datetime, timezone

import numpy as np
import pytest
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import Point, Polygon
from sqlalchemy import inspect, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config.settings import get_settings
from src.db.models import (
    Base,
    Detection,
    DetectionType,
    FeedbackType,
    Image,
    Location,
    ProcessingStatus,
    User,
    UserFeedback,
    UserRole,
    WalkabilityScore,
)

# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
def engine():
    settings = get_settings()
    return create_async_engine(settings.database_url, echo=False)


@pytest.fixture(scope="session")
async def setup_db(engine):
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def session(engine, setup_db):
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()


# ─── Connection & PostGIS ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_postgres_connection(session: AsyncSession):
    result = await session.execute(text("SELECT 1"))
    assert result.scalar() == 1


@pytest.mark.asyncio
async def test_postgis_enabled(session: AsyncSession):
    result = await session.execute(text("SELECT PostGIS_Version()"))
    version = result.scalar()
    assert version is not None


# ─── Schema Validation ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_all_tables_exist(engine, setup_db):
    expected_tables = {"users", "images", "detections", "locations", "walkability_scores", "user_feedbacks"}
    async with engine.connect() as conn:
        table_names = await conn.run_sync(lambda sync_conn: set(inspect(sync_conn).get_table_names()))
    assert expected_tables.issubset(table_names)


@pytest.mark.asyncio
async def test_users_columns(engine, setup_db):
    async with engine.connect() as conn:
        columns = await conn.run_sync(
            lambda sync_conn: {c["name"] for c in inspect(sync_conn).get_columns("users")}
        )
    assert {"user_id", "email", "hashed_password", "role", "created_at", "updated_at"}.issubset(columns)


@pytest.mark.asyncio
async def test_images_columns(engine, setup_db):
    async with engine.connect() as conn:
        columns = await conn.run_sync(
            lambda sync_conn: {c["name"] for c in inspect(sync_conn).get_columns("images")}
        )
    expected = {
        "image_id", "user_id", "original_filename", "storage_path",
        "file_size_bytes", "mime_type", "uploaded_at", "location",
        "image_metadata", "processing_status", "deleted_at",
    }
    assert expected.issubset(columns)


@pytest.mark.asyncio
async def test_detections_columns(engine, setup_db):
    async with engine.connect() as conn:
        columns = await conn.run_sync(
            lambda sync_conn: {c["name"] for c in inspect(sync_conn).get_columns("detections")}
        )
    expected = {
        "detection_id", "image_id", "detection_type", "confidence_score",
        "bounding_box", "location", "detection_metadata", "embedding",
        "caption", "created_at",
    }
    assert expected.issubset(columns)


# ─── CRUD: User ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_user(session: AsyncSession):
    user = User(
        email="test@kalye.dev",
        hashed_password="hashed_pw_123",
        role=UserRole.admin,
    )
    session.add(user)
    await session.flush()

    assert user.user_id is not None
    assert user.created_at is not None
    assert user.role == UserRole.admin


@pytest.mark.asyncio
async def test_user_email_unique(session: AsyncSession):
    user1 = User(email="unique@kalye.dev", hashed_password="pw1")
    user2 = User(email="unique@kalye.dev", hashed_password="pw2")
    session.add(user1)
    await session.flush()
    session.add(user2)
    with pytest.raises(Exception):
        await session.flush()


# ─── CRUD: Image ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_image_with_location(session: AsyncSession):
    user = User(email="img_user@kalye.dev", hashed_password="pw")
    session.add(user)
    await session.flush()

    point = from_shape(Point(121.0320, 14.6507), srid=4326)  # QC Timog
    image = Image(
        user_id=user.user_id,
        original_filename="timog_sidewalk.jpg",
        storage_path="uploads/timog_sidewalk.jpg",
        file_size_bytes=2_500_000,
        mime_type="image/jpeg",
        location=point,
        processing_status=ProcessingStatus.pending,
    )
    session.add(image)
    await session.flush()

    assert image.image_id is not None
    assert image.processing_status == ProcessingStatus.pending


@pytest.mark.asyncio
async def test_image_soft_delete(session: AsyncSession):
    user = User(email="softdel@kalye.dev", hashed_password="pw")
    session.add(user)
    await session.flush()

    image = Image(
        user_id=user.user_id,
        original_filename="to_delete.jpg",
        storage_path="uploads/to_delete.jpg",
        file_size_bytes=1_000_000,
        mime_type="image/jpeg",
    )
    session.add(image)
    await session.flush()

    assert image.deleted_at is None
    image.deleted_at = datetime.now(timezone.utc)
    await session.flush()
    assert image.deleted_at is not None


@pytest.mark.asyncio
async def test_image_jsonb_metadata(session: AsyncSession):
    user = User(email="jsonb@kalye.dev", hashed_password="pw")
    session.add(user)
    await session.flush()

    metadata = {"camera": "iPhone 15", "gps_accuracy": 5.2, "exif": {"iso": 200}}
    image = Image(
        user_id=user.user_id,
        original_filename="meta.jpg",
        storage_path="uploads/meta.jpg",
        file_size_bytes=3_000_000,
        mime_type="image/jpeg",
        image_metadata=metadata,
    )
    session.add(image)
    await session.flush()

    result = await session.execute(select(Image).where(Image.image_id == image.image_id))
    fetched = result.scalar_one()
    assert fetched.image_metadata["camera"] == "iPhone 15"
    assert fetched.image_metadata["exif"]["iso"] == 200


# ─── CRUD: Detection ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_detection(session: AsyncSession):
    user = User(email="det_user@kalye.dev", hashed_password="pw")
    session.add(user)
    await session.flush()

    image = Image(
        user_id=user.user_id,
        original_filename="pothole.jpg",
        storage_path="uploads/pothole.jpg",
        file_size_bytes=2_000_000,
        mime_type="image/jpeg",
    )
    session.add(image)
    await session.flush()

    detection = Detection(
        image_id=image.image_id,
        detection_type=DetectionType.pothole,
        confidence_score=0.87,
        bounding_box={"x": 100, "y": 200, "width": 50, "height": 50},
        location=from_shape(Point(121.0244, 14.5547), srid=4326),
        detection_metadata={"model_version": "yolov8m-v1", "inference_ms": 245},
    )
    session.add(detection)
    await session.flush()

    assert detection.detection_id is not None
    assert detection.confidence_score == 0.87
    assert detection.detection_type == DetectionType.pothole


# ─── CRUD: Location & WalkabilityScore ────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_location_with_polygon(session: AsyncSession):
    polygon = Polygon([
        (121.0, 14.6), (121.1, 14.6), (121.1, 14.7),
        (121.0, 14.7), (121.0, 14.6),
    ])
    location = Location(
        barangay_name="Diliman",
        city="Quezon City",
        geometry=from_shape(polygon, srid=4326),
        population=120000,
    )
    session.add(location)
    await session.flush()

    assert location.location_id is not None


@pytest.mark.asyncio
async def test_create_walkability_score(session: AsyncSession):
    location = Location(barangay_name="Makati Central", city="Makati")
    session.add(location)
    await session.flush()

    score = WalkabilityScore(
        location_id=location.location_id,
        score=82,
        breakdown={
            "sidewalk_coverage": 0.90,
            "obstruction_density": 1.2,
            "ada_compliance": 0.75,
        },
        version="1.0",
    )
    session.add(score)
    await session.flush()

    assert score.score_id is not None
    assert score.score == 82
    assert score.breakdown["sidewalk_coverage"] == 0.90


# ─── CRUD: UserFeedback ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_feedback(session: AsyncSession):
    user = User(email="fb_user@kalye.dev", hashed_password="pw")
    session.add(user)
    await session.flush()

    feedback = UserFeedback(
        user_id=user.user_id,
        detection_id=None,
        feedback_type=FeedbackType.missing_detection,
        comment="There's a pothole here that was not detected",
    )
    session.add(feedback)
    await session.flush()

    assert feedback.feedback_id is not None
    assert feedback.feedback_type == FeedbackType.missing_detection


# ─── Cascade Deletes ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cascade_delete_user_deletes_images(session: AsyncSession):
    user = User(email="cascade@kalye.dev", hashed_password="pw")
    session.add(user)
    await session.flush()

    image = Image(
        user_id=user.user_id,
        original_filename="cascade.jpg",
        storage_path="uploads/cascade.jpg",
        file_size_bytes=1_000_000,
        mime_type="image/jpeg",
    )
    session.add(image)
    await session.flush()
    image_id = image.image_id

    await session.delete(user)
    await session.flush()

    result = await session.execute(select(Image).where(Image.image_id == image_id))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_cascade_delete_image_deletes_detections(session: AsyncSession):
    user = User(email="cascade_det@kalye.dev", hashed_password="pw")
    session.add(user)
    await session.flush()

    image = Image(
        user_id=user.user_id,
        original_filename="cascade_det.jpg",
        storage_path="uploads/cascade_det.jpg",
        file_size_bytes=1_000_000,
        mime_type="image/jpeg",
    )
    session.add(image)
    await session.flush()

    detection = Detection(
        image_id=image.image_id,
        detection_type=DetectionType.missing_sign,
        confidence_score=0.78,
        bounding_box={"x": 10, "y": 20, "width": 30, "height": 30},
    )
    session.add(detection)
    await session.flush()
    det_id = detection.detection_id

    await session.delete(image)
    await session.flush()

    result = await session.execute(select(Detection).where(Detection.detection_id == det_id))
    assert result.scalar_one_or_none() is None


# ─── Geospatial Queries ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_radius_query(session: AsyncSession):
    """Find detections within 1km of a point."""
    user = User(email="geo_user@kalye.dev", hashed_password="pw")
    session.add(user)
    await session.flush()

    image = Image(
        user_id=user.user_id,
        original_filename="geo.jpg",
        storage_path="uploads/geo.jpg",
        file_size_bytes=1_000_000,
        mime_type="image/jpeg",
    )
    session.add(image)
    await session.flush()

    # Detection near QC Timog (14.6507, 121.0320)
    near = Detection(
        image_id=image.image_id,
        detection_type=DetectionType.pothole,
        confidence_score=0.85,
        bounding_box={"x": 0, "y": 0, "width": 50, "height": 50},
        location=from_shape(Point(121.0325, 14.6510), srid=4326),
    )
    # Detection far away in Makati (14.5547, 121.0244)
    far = Detection(
        image_id=image.image_id,
        detection_type=DetectionType.pothole,
        confidence_score=0.90,
        bounding_box={"x": 0, "y": 0, "width": 50, "height": 50},
        location=from_shape(Point(121.0244, 14.5547), srid=4326),
    )
    session.add_all([near, far])
    await session.flush()

    # Query within 1km of QC Timog
    center = from_shape(Point(121.0320, 14.6507), srid=4326)
    query = select(Detection).where(
        Detection.location.isnot(None),
        Detection.location.ST_DWithin(
            center,
            0.01,  # ~1.1km at this latitude
        ),
    )
    result = await session.execute(query)
    nearby = result.scalars().all()

    assert len(nearby) == 1
    assert nearby[0].detection_id == near.detection_id


@pytest.mark.asyncio
async def test_bounding_box_query(session: AsyncSession):
    """Find locations within a bounding box."""
    polygon = Polygon([
        (121.0, 14.6), (121.1, 14.6), (121.1, 14.7),
        (121.0, 14.7), (121.0, 14.6),
    ])
    loc_inside = Location(
        barangay_name="Inside",
        city="Quezon City",
        geometry=from_shape(polygon, srid=4326),
    )
    loc_outside = Location(
        barangay_name="Outside",
        city="Caloocan",
        geometry=from_shape(
            Polygon([(120.9, 14.7), (120.95, 14.7), (120.95, 14.75), (120.9, 14.75), (120.9, 14.7)]),
            srid=4326,
        ),
    )
    session.add_all([loc_inside, loc_outside])
    await session.flush()

    # Bounding box covering QC area
    bbox = from_shape(
        Polygon([(120.99, 14.59), (121.11, 14.59), (121.11, 14.71), (120.99, 14.71), (120.99, 14.59)]),
        srid=4326,
    )
    query = select(Location).where(
        Location.geometry.isnot(None),
        Location.geometry.ST_Intersects(bbox),
    )
    result = await session.execute(query)
    found = result.scalars().all()

    names = {loc.barangay_name for loc in found}
    assert "Inside" in names
    assert "Outside" not in names


@pytest.mark.asyncio
async def test_distance_calculation(session: AsyncSession):
    """Calculate distance between two points."""
    point_a = from_shape(Point(121.0320, 14.6507), srid=4326)  # QC Timog
    point_b = from_shape(Point(121.0244, 14.5547), srid=4326)  # Makati Ayala

    result = await session.execute(
        text("SELECT ST_Distance(:a::geography, :b::geography)").bindparams(a=point_a, b=point_b)
    )
    distance_meters = result.scalar()

    # QC Timog to Makati Ayala is roughly 10-11km
    assert 9000 < distance_meters < 12000


# ─── Spatial Index Validation ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gist_indexes_exist(engine, setup_db):
    async with engine.connect() as conn:
        result = await conn.execute(text("""
            SELECT indexname FROM pg_indexes
            WHERE tablename IN ('images', 'detections', 'locations')
            AND indexdef LIKE '%gist%'
        """))
        index_names = {row[0] for row in result.fetchall()}

    assert "idx_images_location" in index_names
    assert "idx_detections_location" in index_names
    assert "idx_locations_geometry" in index_names


# ─── Timestamp Defaults ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_timestamps_auto_set(session: AsyncSession):
    user = User(email="timestamps@kalye.dev", hashed_password="pw")
    session.add(user)
    await session.flush()

    assert user.created_at is not None
    assert user.updated_at is not None
    assert isinstance(user.created_at, datetime)


# ─── Enum Validation ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_user_roles():
    assert set(UserRole) == {UserRole.admin, UserRole.lgu_user, UserRole.public}


@pytest.mark.asyncio
async def test_processing_statuses():
    assert set(ProcessingStatus) == {
        ProcessingStatus.pending,
        ProcessingStatus.processing,
        ProcessingStatus.completed,
        ProcessingStatus.failed,
    }


@pytest.mark.asyncio
async def test_detection_types():
    expected = {
        DetectionType.pothole,
        DetectionType.sidewalk_obstruction,
        DetectionType.missing_sign,
        DetectionType.curb_ramp,
        DetectionType.broken_sidewalk,
        DetectionType.flooding,
        DetectionType.missing_ramp,
    }
    assert set(DetectionType) == expected


@pytest.mark.asyncio
async def test_feedback_types():
    assert set(FeedbackType) == {
        FeedbackType.correct,
        FeedbackType.incorrect,
        FeedbackType.missing_detection,
    }


# ─── pgvector & RAG Fields ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pgvector_extension_enabled(session: AsyncSession):
    result = await session.execute(text("SELECT extname FROM pg_extension WHERE extname = 'vector'"))
    assert result.scalar() == "vector"


@pytest.mark.asyncio
async def test_detection_with_embedding_and_caption(session: AsyncSession):
    """Test that detection can store a 384-dim vector embedding and caption."""
    user = User(email="embed_user@kalye.dev", hashed_password="pw")
    session.add(user)
    await session.flush()

    image = Image(
        user_id=user.user_id,
        original_filename="embed.jpg",
        storage_path="uploads/embed.jpg",
        file_size_bytes=1_000_000,
        mime_type="image/jpeg",
    )
    session.add(image)
    await session.flush()

    fake_embedding = np.random.rand(384).astype(np.float32).tolist()
    detection = Detection(
        image_id=image.image_id,
        detection_type=DetectionType.pothole,
        confidence_score=0.92,
        bounding_box={"x": 50, "y": 100, "width": 40, "height": 40},
        embedding=fake_embedding,
        caption="A large pothole on a concrete sidewalk near a school.",
    )
    session.add(detection)
    await session.flush()

    result = await session.execute(
        select(Detection).where(Detection.detection_id == detection.detection_id)
    )
    fetched = result.scalar_one()
    assert fetched.caption == "A large pothole on a concrete sidewalk near a school."
    assert len(fetched.embedding) == 384


@pytest.mark.asyncio
async def test_vector_similarity_search(session: AsyncSession):
    """Test pgvector cosine similarity search on detection embeddings."""
    user = User(email="vecsearch@kalye.dev", hashed_password="pw")
    session.add(user)
    await session.flush()

    image = Image(
        user_id=user.user_id,
        original_filename="vecsearch.jpg",
        storage_path="uploads/vecsearch.jpg",
        file_size_bytes=1_000_000,
        mime_type="image/jpeg",
    )
    session.add(image)
    await session.flush()

    # Create two detections with known embeddings
    emb_a = [1.0] + [0.0] * 383  # Points in one direction
    emb_b = [0.0] + [1.0] + [0.0] * 382  # Orthogonal direction

    det_a = Detection(
        image_id=image.image_id,
        detection_type=DetectionType.pothole,
        confidence_score=0.80,
        bounding_box={"x": 0, "y": 0, "width": 10, "height": 10},
        embedding=emb_a,
        caption="Pothole A",
    )
    det_b = Detection(
        image_id=image.image_id,
        detection_type=DetectionType.sidewalk_obstruction,
        confidence_score=0.75,
        bounding_box={"x": 0, "y": 0, "width": 10, "height": 10},
        embedding=emb_b,
        caption="Obstruction B",
    )
    session.add_all([det_a, det_b])
    await session.flush()

    # Query for vectors similar to emb_a using cosine distance
    query_emb = str(emb_a)
    result = await session.execute(
        text(
            "SELECT detection_id, caption FROM detections "
            "WHERE embedding IS NOT NULL "
            "ORDER BY embedding <=> :query_emb LIMIT 1"
        ).bindparams(query_emb=query_emb)
    )
    nearest = result.fetchone()
    assert nearest is not None
    assert nearest[1] == "Pothole A"
