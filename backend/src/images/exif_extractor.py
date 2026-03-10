"""EXIF metadata extraction for uploaded street imagery."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PIL import Image
from PIL.ExifTags import GPSTAGS, TAGS

logger = logging.getLogger(__name__)


class EXIFExtractor:
    """Extract EXIF metadata from images using Pillow.

    Focuses on the fields most relevant for the KALYE platform:
    GPS coordinates, capture timestamp, camera model, and orientation.
    """

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def extract_all(self, image_or_path: Image.Image | Path) -> dict[str, Any]:
        """Return a dictionary of selected EXIF fields.

        Keys returned (when available):
            - ``gps_latitude``  (float, decimal degrees, positive = N)
            - ``gps_longitude`` (float, decimal degrees, positive = E)
            - ``timestamp``     (str, original DateTimeOriginal value)
            - ``camera_model``  (str)
            - ``orientation``   (int, EXIF orientation tag value)
        """
        image = self._open(image_or_path)
        exif_data = self._raw_exif(image)

        result: dict[str, Any] = {}

        # GPS
        coords = self.extract_gps_coordinates(image)
        if coords is not None:
            result["gps_latitude"] = coords[0]
            result["gps_longitude"] = coords[1]

        # Timestamp
        timestamp = exif_data.get("DateTimeOriginal") or exif_data.get("DateTime")
        if timestamp is not None:
            result["timestamp"] = str(timestamp)

        # Camera model
        model = exif_data.get("Model")
        if model is not None:
            result["camera_model"] = str(model)

        # Orientation
        orientation = exif_data.get("Orientation")
        if orientation is not None:
            result["orientation"] = int(orientation)

        logger.debug("Extracted EXIF metadata: %s", result)
        return result

    def extract_gps_coordinates(
        self, image_or_path: Image.Image | Path
    ) -> tuple[float, float] | None:
        """Extract GPS coordinates as ``(latitude, longitude)`` in decimal degrees.

        Returns ``None`` when GPS data is absent or incomplete.
        """
        image = self._open(image_or_path)
        exif_data = self._raw_exif(image)
        gps_info = exif_data.get("GPSInfo")
        if not gps_info:
            logger.debug("No GPSInfo found in EXIF data.")
            return None

        # Decode GPSInfo sub-tags
        gps: dict[str, Any] = {}
        for tag_id, value in gps_info.items():
            tag_name = GPSTAGS.get(tag_id, tag_id)
            gps[tag_name] = value

        try:
            lat = self._dms_to_decimal(
                gps["GPSLatitude"], gps.get("GPSLatitudeRef", "N")
            )
            lon = self._dms_to_decimal(
                gps["GPSLongitude"], gps.get("GPSLongitudeRef", "E")
            )
        except (KeyError, TypeError, ZeroDivisionError) as exc:
            logger.warning("Incomplete GPS data in EXIF: %s", exc)
            return None

        logger.debug("GPS coordinates: (%f, %f)", lat, lon)
        return (lat, lon)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _dms_to_decimal(dms: tuple, ref: str) -> float:
        """Convert degrees/minutes/seconds tuple to decimal degrees.

        Parameters
        ----------
        dms:
            A 3-element tuple of ``(degrees, minutes, seconds)``.  Each
            element may be a number or a ``PIL.TiffImagePlugin.IFDRational``.
        ref:
            Cardinal direction reference (``N``, ``S``, ``E``, or ``W``).
        """
        degrees = float(dms[0])
        minutes = float(dms[1])
        seconds = float(dms[2])

        decimal = degrees + minutes / 60.0 + seconds / 3600.0

        if ref in ("S", "W"):
            decimal = -decimal

        return decimal

    @staticmethod
    def _open(image_or_path: Image.Image | Path) -> Image.Image:
        if isinstance(image_or_path, Path):
            return Image.open(image_or_path)
        return image_or_path

    @staticmethod
    def _raw_exif(image: Image.Image) -> dict[str, Any]:
        """Return a tag-name-keyed dict of the image's EXIF data."""
        raw = image.getexif()
        decoded: dict[str, Any] = {}
        for tag_id, value in raw.items():
            tag_name = TAGS.get(tag_id, tag_id)
            decoded[tag_name] = value
        return decoded
