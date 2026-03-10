"""Image validation for the KALYE upload pipeline."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import BinaryIO

from PIL import Image

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when an image fails validation."""


class ImageValidator:
    """Validates uploaded images against KALYE platform requirements.

    Rules:
        - Allowed formats: JPEG, PNG, WEBP
        - Max file size: 10 MB
        - Min resolution: 640x480
        - GPS coordinates must fall inside Metro Manila bounding box
        - Image must not be corrupted
    """

    ALLOWED_FORMATS: set[str] = {"JPEG", "PNG", "WEBP"}
    MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB
    MIN_WIDTH: int = 640
    MIN_HEIGHT: int = 480

    # Metro Manila bounding box
    MM_LAT_MIN: float = 14.4
    MM_LAT_MAX: float = 14.8
    MM_LON_MIN: float = 120.9
    MM_LON_MAX: float = 121.1

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def validate_format(self, image: Image.Image) -> None:
        """Validate that the image format is in the allowed set."""
        fmt = image.format
        if fmt is None or fmt.upper() not in self.ALLOWED_FORMATS:
            raise ValidationError(
                f"Unsupported image format '{fmt}'. "
                f"Allowed formats: {', '.join(sorted(self.ALLOWED_FORMATS))}"
            )
        logger.debug("Format validation passed: %s", fmt)

    def validate_size(self, file: BinaryIO | Path | int) -> None:
        """Validate that the file does not exceed the maximum size.

        Accepts a file-like object (seekable), a ``Path``, or an integer
        representing the size in bytes.
        """
        if isinstance(file, int):
            size = file
        elif isinstance(file, Path):
            size = file.stat().st_size
        else:
            # file-like object
            pos = file.tell()
            file.seek(0, 2)
            size = file.tell()
            file.seek(pos)

        if size > self.MAX_FILE_SIZE_BYTES:
            raise ValidationError(
                f"File size {size} bytes exceeds maximum allowed "
                f"size of {self.MAX_FILE_SIZE_BYTES} bytes (10 MB)."
            )
        logger.debug("Size validation passed: %d bytes", size)

    def validate_resolution(self, image: Image.Image) -> None:
        """Validate that the image meets minimum resolution requirements."""
        width, height = image.size
        if width < self.MIN_WIDTH or height < self.MIN_HEIGHT:
            raise ValidationError(
                f"Image resolution {width}x{height} is below the minimum "
                f"required resolution of {self.MIN_WIDTH}x{self.MIN_HEIGHT}."
            )
        logger.debug("Resolution validation passed: %dx%d", width, height)

    def validate_coordinates(self, latitude: float, longitude: float) -> None:
        """Validate that GPS coordinates fall within the Metro Manila bounding box."""
        if not (self.MM_LAT_MIN <= latitude <= self.MM_LAT_MAX):
            raise ValidationError(
                f"Latitude {latitude} is outside Metro Manila bounds "
                f"({self.MM_LAT_MIN} - {self.MM_LAT_MAX})."
            )
        if not (self.MM_LON_MIN <= longitude <= self.MM_LON_MAX):
            raise ValidationError(
                f"Longitude {longitude} is outside Metro Manila bounds "
                f"({self.MM_LON_MIN} - {self.MM_LON_MAX})."
            )
        logger.debug("Coordinate validation passed: (%f, %f)", latitude, longitude)

    def validate_image(
        self,
        file: BinaryIO | Path,
        *,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> Image.Image:
        """Run all validations on an image file.

        Parameters
        ----------
        file:
            A seekable file-like object or a ``Path`` to the image on disk.
        latitude, longitude:
            Optional GPS coordinates. If both are provided they are validated
            against the Metro Manila bounding box.

        Returns
        -------
        PIL.Image.Image
            The opened (and verified) PIL Image instance.

        Raises
        ------
        ValidationError
            If any check fails.
        """
        # --- size ---
        self.validate_size(file)

        # --- corruption + format ---
        try:
            if isinstance(file, Path):
                image = Image.open(file)
            else:
                file.seek(0)
                image = Image.open(file)
            image.verify()

            # Re-open because verify() can leave the image in an unusable state.
            if isinstance(file, Path):
                image = Image.open(file)
            else:
                file.seek(0)
                image = Image.open(file)
            image.load()
        except Exception as exc:
            raise ValidationError(f"Image is corrupted or unreadable: {exc}") from exc

        # --- format ---
        self.validate_format(image)

        # --- resolution ---
        self.validate_resolution(image)

        # --- coordinates (optional) ---
        if latitude is not None and longitude is not None:
            self.validate_coordinates(latitude, longitude)

        logger.info("Image passed all validation checks.")
        return image
