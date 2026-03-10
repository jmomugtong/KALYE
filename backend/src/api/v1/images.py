"""Image upload and retrieval endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict

router = APIRouter(prefix="/api/v1/images", tags=["images"])


# ── Response Models ──────────────────────────────────────────────────────────


class ImageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    image_id: str
    user_id: str
    original_filename: str
    storage_path: str
    file_size_bytes: int
    mime_type: str
    uploaded_at: datetime
    processing_status: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class DetectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    detection_id: str
    image_id: str
    detection_type: str
    confidence_score: float
    bounding_box: dict
    caption: Optional[str] = None
    created_at: datetime


class ImageUploadResponse(BaseModel):
    image_id: str
    status: str
    message: str


class BatchUploadResponse(BaseModel):
    uploaded: List[ImageUploadResponse]
    errors: List[dict]


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.post("/upload", response_model=ImageUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_image(file: UploadFile = File(...)):
    """Upload a single street image for analysis."""
    if file.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file.content_type}",
        )

    image_id = str(uuid.uuid4())

    # TODO: persist to MinIO via storage_manager and create DB record
    return ImageUploadResponse(
        image_id=image_id,
        status="pending",
        message="Image queued for processing",
    )


@router.post("/upload-batch", response_model=BatchUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_batch(files: List[UploadFile] = File(...)):
    """Upload up to 10 images in a single request."""
    if len(files) > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 10 images per batch upload",
        )

    uploaded: List[ImageUploadResponse] = []
    errors: List[dict] = []

    for file in files:
        if file.content_type not in ("image/jpeg", "image/png", "image/webp"):
            errors.append(
                {"filename": file.filename, "error": f"Unsupported type: {file.content_type}"}
            )
            continue

        image_id = str(uuid.uuid4())
        uploaded.append(
            ImageUploadResponse(
                image_id=image_id,
                status="pending",
                message="Image queued for processing",
            )
        )

    return BatchUploadResponse(uploaded=uploaded, errors=errors)


@router.get("/{image_id}", response_model=ImageResponse)
async def get_image(image_id: str):
    """Retrieve image metadata by ID."""
    # TODO: query database for image record
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Image {image_id} not found",
    )


@router.get("/{image_id}/detections", response_model=List[DetectionResponse])
async def get_image_detections(image_id: str):
    """Get all detections associated with an image."""
    # TODO: query database for detections
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Image {image_id} not found",
    )
