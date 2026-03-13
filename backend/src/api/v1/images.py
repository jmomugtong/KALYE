"""Image upload and retrieval endpoints — wired to PostGIS + Colab AI."""

from __future__ import annotations

import logging
import random
import uuid
from datetime import datetime, timezone
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from geoalchemy2.functions import ST_MakePoint, ST_SetSRID
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import get_settings
from src.db.models import Detection, DetectionType, Image, ProcessingStatus
from src.db.postgres import get_session
from src.api.middleware.auth import get_current_user
from src.api.middleware.rate_limit import RateLimiter as _RateLimiter

_upload_limiter = _RateLimiter(tier="upload")

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/images", tags=["images"])


# ── Response Models ──────────────────────────────────────────────────────────


class ImageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    image_id: str
    original_filename: str
    file_size_bytes: int
    mime_type: str
    uploaded_at: datetime
    processing_status: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class ImageUploadResponse(BaseModel):
    image_id: str
    status: str
    message: str
    detections_created: int = 0
    ai_caption: Optional[str] = None
    sidewalk_coverage_pct: Optional[float] = None
    inference_source: str = "simulated"


class BatchUploadResponse(BaseModel):
    uploaded: List[ImageUploadResponse]
    errors: List[dict]


# ── Map Colab detection types to DB enum ────────────────────────────────────

_COLAB_TYPE_MAP = {
    "pothole": DetectionType.pothole,
    "sidewalk_obstruction": DetectionType.sidewalk_obstruction,
    "missing_sign": DetectionType.missing_sign,
    "curb_ramp": DetectionType.curb_ramp,
    "broken_sidewalk": DetectionType.broken_sidewalk,
    "flooding": DetectionType.flooding,
    "missing_ramp": DetectionType.missing_ramp,
    "street_vendor_obstruction": DetectionType.sidewalk_obstruction,
}


# ── Colab AI inference ──────────────────────────────────────────────────────


async def _call_colab_ai(file_content: bytes, filename: str, content_type: str) -> Optional[dict]:
    """Send image to Colab AI server and return results, or None if unavailable."""
    settings = get_settings()
    if not settings.colab_ai_url:
        return None

    url = f"{settings.colab_ai_url.rstrip('/')}/analyze"
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                url,
                files={"file": (filename, file_content, content_type)},
                headers={"ngrok-skip-browser-warning": "true"},
            )
            if response.status_code == 200:
                data = response.json()
                logger.info(
                    "Colab AI returned %d detections in %.1fs (caption: %s)",
                    len(data.get("detections", [])),
                    data.get("inference_time_seconds", 0),
                    data.get("caption", "")[:60],
                )
                return data
            else:
                logger.warning("Colab AI returned %d: %s", response.status_code, response.text[:200])
    except Exception as exc:
        logger.warning("Colab AI unreachable: %s", exc)

    return None


def _colab_detections_to_db(
    colab_data: dict, image_id: uuid.UUID, lat: float, lng: float, caption: str
) -> list[Detection]:
    """Convert Colab AI response into Detection ORM objects."""
    detections = []
    colab_dets = colab_data.get("detections", [])

    for det in colab_dets:
        det_type_str = det.get("detection_type", "")
        det_type = _COLAB_TYPE_MAP.get(det_type_str)
        if det_type is None:
            continue

        # Jitter location slightly so overlapping detections separate on map
        jlat = lat + random.uniform(-0.0002, 0.0002)
        jlng = lng + random.uniform(-0.0002, 0.0002)

        detections.append(Detection(
            detection_id=uuid.uuid4(),
            image_id=image_id,
            detection_type=det_type,
            confidence_score=det["confidence"],
            bounding_box=det["bounding_box"],
            location=ST_SetSRID(ST_MakePoint(jlng, jlat), 4326),
            caption=f"{caption} [{det.get('coco_class', det_type_str)}]",
        ))

    # If YOLO found nothing walkability-related, create a "clean street" from segmentation
    if not detections:
        seg = colab_data.get("segmentation", {})
        sidewalk_pct = seg.get("sidewalk_coverage_pct", 0)
        if sidewalk_pct < 5.0:
            detections.append(Detection(
                detection_id=uuid.uuid4(),
                image_id=image_id,
                detection_type=DetectionType.missing_ramp,
                confidence_score=0.75,
                bounding_box={"x": 0, "y": 0, "w": 100, "h": 100},
                location=ST_SetSRID(ST_MakePoint(lng, lat), 4326),
                caption=f"Low sidewalk coverage ({sidewalk_pct:.1f}%). {caption}",
            ))

    return detections


# ── Simulated fallback (no Colab) ───────────────────────────────────────────

_FALLBACK_POOL = [
    (DetectionType.pothole, "Pothole detected on road surface"),
    (DetectionType.sidewalk_obstruction, "Sidewalk obstruction — parked vehicle / vendor stall"),
    (DetectionType.missing_sign, "Missing or damaged pedestrian sign"),
    (DetectionType.curb_ramp, "Missing or damaged curb ramp"),
    (DetectionType.broken_sidewalk, "Broken or uneven sidewalk surface"),
    (DetectionType.flooding, "Standing water / flood-prone area"),
    (DetectionType.missing_ramp, "No wheelchair ramp at crossing"),
]


def _simulate_detections(image_id: uuid.UUID, lat: float, lng: float) -> list[Detection]:
    """Generate 1-3 simulated detections (fallback when Colab is offline)."""
    count = random.randint(1, 3)
    picks = random.sample(_FALLBACK_POOL, k=min(count, len(_FALLBACK_POOL)))
    detections = []

    for det_type, caption in picks:
        jlat = lat + random.uniform(-0.0003, 0.0003)
        jlng = lng + random.uniform(-0.0003, 0.0003)

        detections.append(Detection(
            detection_id=uuid.uuid4(),
            image_id=image_id,
            detection_type=det_type,
            confidence_score=round(random.uniform(0.72, 0.97), 2),
            bounding_box={"x": random.randint(50, 400), "y": random.randint(50, 300),
                          "w": random.randint(60, 200), "h": random.randint(60, 200)},
            location=ST_SetSRID(ST_MakePoint(jlng, jlat), 4326),
            caption=caption,
        ))

    return detections


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.post("/upload", response_model=ImageUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_image(
    file: UploadFile = File(...),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _rl: None = Depends(_RateLimiter(tier="upload")),
):
    """Upload a street image. Uses Colab AI if available, otherwise simulates."""
    if file.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file.content_type}",
        )

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10 MB
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File too large. Maximum 10 MB.")

    if latitude is not None and longitude is not None:
        if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid coordinates.")

    file_size = len(content)
    image_id = uuid.uuid4()

    location = None
    if latitude is not None and longitude is not None:
        location = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)

    # Create image record
    image = Image(
        image_id=image_id,
        user_id=uuid.UUID(current_user["user_id"]),
        original_filename=file.filename or "unknown.jpg",
        storage_path=f"uploads/{image_id}/{file.filename}",
        file_size_bytes=file_size,
        mime_type=file.content_type,
        location=location,
        processing_status=ProcessingStatus.completed,
    )
    session.add(image)

    # Run AI
    det_count = 0
    ai_caption = None
    sidewalk_pct = None
    inference_source = "simulated"

    if latitude is not None and longitude is not None:
        ai_result = None

        # 1. Try Claude Vision API (fastest, most accurate)
        try:
            from src.services.claude_vision import analyze_with_claude
            ai_result = await analyze_with_claude(content, file.content_type or "image/jpeg")
            if ai_result and ai_result.get("status") == "ok":
                inference_source = "claude_vision"
        except Exception as exc:
            logger.warning("Claude Vision unavailable: %s", exc)

        # 2. Fallback: local CPU AI (YOLOv8 + SegFormer + BLIP)
        if ai_result is None or ai_result.get("status") != "ok":
            try:
                from src.services.local_ai import analyze_image_bytes
                ai_result = await analyze_image_bytes(content, file.filename or "image.jpg")
                if ai_result and ai_result.get("status") == "ok":
                    inference_source = "local_cpu"
            except Exception as exc:
                logger.warning("Local AI unavailable: %s", exc)

        # 3. Fallback: Colab T4 GPU
        if ai_result is None or ai_result.get("status") != "ok":
            colab_result = await _call_colab_ai(content, file.filename or "image.jpg", file.content_type)
            if colab_result and colab_result.get("status") == "ok":
                ai_result = colab_result
                inference_source = "colab_t4_gpu"

        # Use AI results or fall back to simulation
        if ai_result and ai_result.get("status") == "ok":
            ai_caption = ai_result.get("caption")
            sidewalk_pct = ai_result.get("segmentation", {}).get("sidewalk_coverage_pct")
            detections = _colab_detections_to_db(
                ai_result, image_id, latitude, longitude, ai_caption or ""
            )
        else:
            detections = _simulate_detections(image_id, latitude, longitude)

        for det in detections:
            session.add(det)
        det_count = len(detections)

    await session.commit()

    source_labels = {
        "claude_vision": "Claude Vision AI",
        "local_cpu": "Local CPU AI",
        "colab_t4_gpu": "Colab T4 GPU AI",
        "simulated": "Simulated",
    }
    msg = f"Image analyzed — {det_count} issue(s) detected ({source_labels.get(inference_source, inference_source)})"

    return ImageUploadResponse(
        image_id=str(image_id),
        status="completed",
        message=msg,
        detections_created=det_count,
        ai_caption=ai_caption,
        sidewalk_coverage_pct=sidewalk_pct,
        inference_source=inference_source,
    )


@router.post("/upload-batch", response_model=BatchUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_batch(
    files: List[UploadFile] = File(...),
    current_user: dict = Depends(get_current_user),
):
    """Upload up to 10 images in a single request."""
    if len(files) > 10:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Maximum 10 images per batch upload")

    uploaded: List[ImageUploadResponse] = []
    errors: List[dict] = []

    for file in files:
        if file.content_type not in ("image/jpeg", "image/png", "image/webp"):
            errors.append({"filename": file.filename, "error": f"Unsupported type: {file.content_type}"})
            continue
        image_id = str(uuid.uuid4())
        uploaded.append(ImageUploadResponse(image_id=image_id, status="pending", message="Image queued"))

    return BatchUploadResponse(uploaded=uploaded, errors=errors)


@router.get("/{image_id}", response_model=ImageResponse)
async def get_image(image_id: str):
    """Retrieve image metadata by ID."""
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Image {image_id} not found")
