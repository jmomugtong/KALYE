"""Orchestrates the full image upload workflow for the KALYE platform."""

from __future__ import annotations

import logging
import tempfile
import uuid
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import UploadFile

from src.images.exif_extractor import EXIFExtractor
from src.images.image_processor import ImageProcessor
from src.images.image_validator import ImageValidator, ValidationError

logger = logging.getLogger(__name__)


class ImageUploader:
    """High-level handler that validates, extracts metadata, preprocesses,
    and persists an uploaded image.
    """

    def __init__(
        self,
        upload_dir: Path | None = None,
    ) -> None:
        self.validator = ImageValidator()
        self.extractor = EXIFExtractor()
        self.processor = ImageProcessor()
        self.upload_dir = upload_dir or Path(tempfile.gettempdir()) / "kalye_uploads"
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    async def validate_file(self, file: UploadFile) -> bool:
        """Validate an ``UploadFile`` against all image rules.

        Returns ``True`` if the file passes validation.

        Raises
        ------
        ValidationError
            If the file fails any validation check.
        """
        contents = await file.read()
        await file.seek(0)

        import io

        buf = io.BytesIO(contents)
        self.validator.validate_image(buf)
        logger.info("File '%s' passed validation.", file.filename)
        return True

    def extract_exif(self, file_path: Path) -> dict[str, Any]:
        """Extract EXIF metadata from an image on disk."""
        exif = self.extractor.extract_all(file_path)
        logger.info("Extracted EXIF from %s: %s", file_path, exif)
        return exif

    def extract_gps_coordinates(
        self, exif: dict[str, Any]
    ) -> tuple[float, float] | None:
        """Pull GPS coordinates from an already-extracted EXIF dict.

        Returns ``(latitude, longitude)`` or ``None``.
        """
        lat = exif.get("gps_latitude")
        lon = exif.get("gps_longitude")
        if lat is not None and lon is not None:
            return (float(lat), float(lon))
        return None

    def preprocess_image(self, file_path: Path) -> Path:
        """Run the preprocessing pipeline (resize, compress, strip metadata)."""
        output_path = file_path.with_suffix(".processed.jpg")
        result = self.processor.preprocess(file_path, output_path)
        logger.info("Preprocessed image: %s -> %s", file_path, result)
        return result

    async def handle_upload(
        self, file: UploadFile, user_id: UUID
    ) -> dict[str, Any]:
        """Full upload orchestration.

        Steps:
            1. Validate the uploaded file.
            2. Persist raw file to a temp location.
            3. Extract EXIF / GPS metadata.
            4. Optionally validate GPS coordinates.
            5. Preprocess (resize, compress, strip metadata).
            6. Return a result dict with paths and metadata.

        Returns
        -------
        dict
            Keys: ``upload_id``, ``user_id``, ``original_path``,
            ``processed_path``, ``exif``, ``gps_coordinates``.
        """
        upload_id = uuid.uuid4()
        logger.info(
            "Starting upload %s for user %s (filename=%s)",
            upload_id,
            user_id,
            file.filename,
        )

        # 1. Validate
        await self.validate_file(file)

        # 2. Save raw file
        raw_path = self.upload_dir / f"{upload_id}_raw{self._suffix(file.filename)}"
        contents = await file.read()
        raw_path.write_bytes(contents)
        logger.info("Saved raw upload to %s (%d bytes)", raw_path, len(contents))

        # 3. EXIF extraction
        exif = self.extract_exif(raw_path)

        # 4. GPS validation (non-fatal – coordinates may be absent)
        gps = self.extract_gps_coordinates(exif)
        if gps is not None:
            try:
                self.validator.validate_coordinates(gps[0], gps[1])
            except ValidationError:
                logger.warning(
                    "GPS coordinates (%f, %f) are outside Metro Manila bounds. "
                    "Proceeding without location.",
                    gps[0],
                    gps[1],
                )
                gps = None

        # 5. Preprocess
        processed_path = self.preprocess_image(raw_path)

        result: dict[str, Any] = {
            "upload_id": str(upload_id),
            "user_id": str(user_id),
            "original_path": str(raw_path),
            "processed_path": str(processed_path),
            "exif": exif,
            "gps_coordinates": gps,
        }

        logger.info("Upload %s completed successfully.", upload_id)
        return result

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _suffix(filename: str | None) -> str:
        if filename:
            return Path(filename).suffix
        return ".jpg"
