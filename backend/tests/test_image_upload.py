"""Tests for the KALYE Phase 3 – Image Upload & Preprocessing pipeline."""

from __future__ import annotations

import io
import struct
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from PIL import Image

from src.images.exif_extractor import EXIFExtractor
from src.images.image_processor import ImageProcessor
from src.images.image_validator import ImageValidator, ValidationError
from src.images.upload_handler import ImageUploader

# ====================================================================== #
# Fixtures
# ====================================================================== #


@pytest.fixture()
def tmp_dir(tmp_path: Path) -> Path:
    """Provide a temporary directory for test artifacts."""
    return tmp_path


def _make_image(
    width: int = 800,
    height: int = 600,
    fmt: str = "JPEG",
    *,
    tmp_dir: Path | None = None,
) -> Path:
    """Create a minimal test image on disk and return its path."""
    img = Image.new("RGB", (width, height), color="blue")
    suffix = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}.get(fmt, ".jpg")
    if tmp_dir is None:
        tmp_dir = Path(tempfile.mkdtemp())
    path = tmp_dir / f"test_image{suffix}"
    img.save(path, format=fmt)
    return path


def _make_image_bytes(
    width: int = 800,
    height: int = 600,
    fmt: str = "JPEG",
) -> bytes:
    """Return raw image bytes for a simple test image."""
    img = Image.new("RGB", (width, height), color="red")
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def _make_upload_file(
    content: bytes,
    filename: str = "photo.jpg",
    content_type: str = "image/jpeg",
) -> Any:
    """Build a minimal UploadFile-like object for testing."""
    from fastapi import UploadFile

    return UploadFile(
        filename=filename,
        file=io.BytesIO(content),
        headers={"content-type": content_type},
    )


# ====================================================================== #
# ImageValidator tests
# ====================================================================== #


class TestImageValidatorFormat:
    """Validate format acceptance and rejection."""

    def test_jpeg_accepted(self, tmp_dir: Path) -> None:
        path = _make_image(fmt="JPEG", tmp_dir=tmp_dir)
        validator = ImageValidator()
        img = Image.open(path)
        validator.validate_format(img)  # should not raise

    def test_png_accepted(self, tmp_dir: Path) -> None:
        path = _make_image(fmt="PNG", tmp_dir=tmp_dir)
        validator = ImageValidator()
        img = Image.open(path)
        validator.validate_format(img)

    def test_webp_accepted(self, tmp_dir: Path) -> None:
        path = _make_image(fmt="WEBP", tmp_dir=tmp_dir)
        validator = ImageValidator()
        img = Image.open(path)
        validator.validate_format(img)

    def test_txt_rejected(self, tmp_dir: Path) -> None:
        """A plain-text file must fail format validation."""
        txt_path = tmp_dir / "not_an_image.txt"
        txt_path.write_text("hello world")
        validator = ImageValidator()
        with pytest.raises(ValidationError, match="corrupted or unreadable"):
            validator.validate_image(txt_path)

    def test_bmp_rejected(self, tmp_dir: Path) -> None:
        """BMP is a valid image but not in the allowed set."""
        img = Image.new("RGB", (800, 600), color="green")
        bmp_path = tmp_dir / "test.bmp"
        img.save(bmp_path, format="BMP")
        validator = ImageValidator()
        with pytest.raises(ValidationError, match="Unsupported image format"):
            validator.validate_image(bmp_path)


class TestImageValidatorSize:
    """Validate file size checks."""

    def test_within_limit(self) -> None:
        validator = ImageValidator()
        validator.validate_size(5 * 1024 * 1024)  # 5 MB – ok

    def test_exceeds_limit(self) -> None:
        validator = ImageValidator()
        with pytest.raises(ValidationError, match="exceeds maximum"):
            validator.validate_size(11 * 1024 * 1024)

    def test_exactly_at_limit(self) -> None:
        validator = ImageValidator()
        validator.validate_size(10 * 1024 * 1024)  # exactly 10 MB – ok

    def test_large_file_rejected(self, tmp_dir: Path) -> None:
        """An actual file > 10 MB should be rejected via validate_image."""
        path = _make_image(width=800, height=600, tmp_dir=tmp_dir)
        validator = ImageValidator()
        # Monkey-patch the max size to something tiny to avoid creating a
        # real 10 MB file in tests.
        validator.MAX_FILE_SIZE_BYTES = 100
        with pytest.raises(ValidationError, match="exceeds maximum"):
            validator.validate_image(path)


class TestImageValidatorResolution:
    """Validate minimum resolution checks."""

    def test_valid_resolution(self) -> None:
        validator = ImageValidator()
        img = Image.new("RGB", (1024, 768))
        validator.validate_resolution(img)

    def test_too_small(self) -> None:
        validator = ImageValidator()
        img = Image.new("RGB", (320, 240))
        with pytest.raises(ValidationError, match="below the minimum"):
            validator.validate_resolution(img)

    def test_width_too_small(self) -> None:
        validator = ImageValidator()
        img = Image.new("RGB", (100, 600))
        with pytest.raises(ValidationError, match="below the minimum"):
            validator.validate_resolution(img)


class TestImageValidatorCorruption:
    """Detect corrupt image data."""

    def test_corrupt_file(self, tmp_dir: Path) -> None:
        path = tmp_dir / "corrupt.jpg"
        path.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
        validator = ImageValidator()
        with pytest.raises(ValidationError, match="corrupted or unreadable"):
            validator.validate_image(path)

    def test_truncated_png(self, tmp_dir: Path) -> None:
        """A truncated PNG should be detected as corrupt."""
        good_path = _make_image(fmt="PNG", tmp_dir=tmp_dir)
        data = good_path.read_bytes()
        truncated_path = tmp_dir / "truncated.png"
        truncated_path.write_bytes(data[: len(data) // 4])
        validator = ImageValidator()
        with pytest.raises(ValidationError, match="corrupted or unreadable"):
            validator.validate_image(truncated_path)


class TestImageValidatorCoordinates:
    """Validate Metro Manila bounding box checks."""

    def test_inside_metro_manila(self) -> None:
        validator = ImageValidator()
        validator.validate_coordinates(14.5995, 120.9842)  # Manila

    def test_outside_latitude(self) -> None:
        validator = ImageValidator()
        with pytest.raises(ValidationError, match="Latitude.*outside"):
            validator.validate_coordinates(10.0, 121.0)

    def test_outside_longitude(self) -> None:
        validator = ImageValidator()
        with pytest.raises(ValidationError, match="Longitude.*outside"):
            validator.validate_coordinates(14.5, 125.0)

    def test_boundary_values(self) -> None:
        validator = ImageValidator()
        validator.validate_coordinates(14.4, 120.9)  # min corner
        validator.validate_coordinates(14.8, 121.1)  # max corner


# ====================================================================== #
# EXIFExtractor tests
# ====================================================================== #


class TestEXIFExtractor:
    """Test EXIF extraction and DMS conversion."""

    def test_dms_to_decimal_north_east(self) -> None:
        extractor = EXIFExtractor()
        # 14 degrees, 35 minutes, 58.2 seconds N
        result = extractor._dms_to_decimal((14, 35, 58.2), "N")
        assert abs(result - 14.5995) < 0.001

    def test_dms_to_decimal_south(self) -> None:
        extractor = EXIFExtractor()
        result = extractor._dms_to_decimal((33, 51, 54.0), "S")
        assert result < 0
        assert abs(result - (-33.865)) < 0.001

    def test_dms_to_decimal_west(self) -> None:
        extractor = EXIFExtractor()
        result = extractor._dms_to_decimal((118, 14, 24.0), "W")
        assert result < 0
        assert abs(result - (-118.24)) < 0.001

    def test_extract_all_no_exif(self, tmp_dir: Path) -> None:
        """An image without EXIF data should return an empty dict."""
        path = _make_image(tmp_dir=tmp_dir)
        extractor = EXIFExtractor()
        result = extractor.extract_all(path)
        # Programmatically generated images have no EXIF.
        assert isinstance(result, dict)
        assert "gps_latitude" not in result

    def test_extract_gps_returns_none_when_absent(self, tmp_dir: Path) -> None:
        path = _make_image(tmp_dir=tmp_dir)
        extractor = EXIFExtractor()
        coords = extractor.extract_gps_coordinates(path)
        assert coords is None

    def test_extract_gps_with_mock_exif(self, tmp_dir: Path) -> None:
        """Inject fake GPS EXIF data and verify extraction."""
        path = _make_image(tmp_dir=tmp_dir)
        extractor = EXIFExtractor()

        fake_gps = {
            "GPSLatitude": (14, 35, 58.2),
            "GPSLatitudeRef": "N",
            "GPSLongitude": (120, 59, 3.12),
            "GPSLongitudeRef": "E",
        }

        with patch.object(extractor, "_raw_exif") as mock_exif:
            mock_exif.return_value = {"GPSInfo": fake_gps}
            # Need to patch GPSTAGS resolution: the mock GPSInfo uses
            # string keys directly, so we also need to make items()
            # work as expected. We patch extract_gps_coordinates to
            # parse a dict keyed by names.
            coords = extractor.extract_gps_coordinates(path)

        # Since our mock returns string keys in GPSInfo and the
        # code uses GPSTAGS.get(tag_id, tag_id), string keys will
        # pass through as-is, matching the expected key names.
        assert coords is not None
        lat, lon = coords
        assert abs(lat - 14.5995) < 0.001
        assert abs(lon - 120.984_2) < 0.01

    def test_extract_all_with_mock_exif(self, tmp_dir: Path) -> None:
        """Full extract_all with mocked EXIF."""
        path = _make_image(tmp_dir=tmp_dir)
        extractor = EXIFExtractor()

        fake_gps = {
            "GPSLatitude": (14, 35, 58.2),
            "GPSLatitudeRef": "N",
            "GPSLongitude": (120, 59, 3.12),
            "GPSLongitudeRef": "E",
        }

        with patch.object(extractor, "_raw_exif") as mock_exif:
            mock_exif.return_value = {
                "GPSInfo": fake_gps,
                "DateTimeOriginal": "2025:03:10 14:30:00",
                "Model": "SM-S918B",
                "Orientation": 1,
            }
            result = extractor.extract_all(path)

        assert result["gps_latitude"] == pytest.approx(14.5995, abs=0.001)
        assert result["timestamp"] == "2025:03:10 14:30:00"
        assert result["camera_model"] == "SM-S918B"
        assert result["orientation"] == 1


# ====================================================================== #
# ImageProcessor tests
# ====================================================================== #


class TestImageProcessor:
    """Test resize, compress, and metadata stripping."""

    def test_resize_within_bounds(self) -> None:
        """An image already within bounds should not be resized."""
        processor = ImageProcessor()
        img = Image.new("RGB", (1280, 720))
        result = processor.resize_image(img)
        assert result.size == (1280, 720)

    def test_resize_maintains_aspect_ratio(self) -> None:
        """A large image should be resized while preserving aspect ratio."""
        processor = ImageProcessor()
        img = Image.new("RGB", (3840, 2160))  # 16:9 4K
        result = processor.resize_image(img)
        w, h = result.size
        assert w <= processor.MAX_WIDTH
        assert h <= processor.MAX_HEIGHT
        # Check aspect ratio is preserved (16:9 = 1.777...)
        original_ratio = 3840 / 2160
        new_ratio = w / h
        assert abs(original_ratio - new_ratio) < 0.01

    def test_resize_wide_image(self) -> None:
        """A very wide image should be constrained by width."""
        processor = ImageProcessor()
        img = Image.new("RGB", (5000, 500))
        result = processor.resize_image(img)
        w, h = result.size
        assert w <= processor.MAX_WIDTH
        assert h <= processor.MAX_HEIGHT

    def test_resize_tall_image(self) -> None:
        """A very tall image should be constrained by height."""
        processor = ImageProcessor()
        img = Image.new("RGB", (500, 3000))
        result = processor.resize_image(img)
        w, h = result.size
        assert w <= processor.MAX_WIDTH
        assert h <= processor.MAX_HEIGHT

    def test_compress_creates_jpeg(self, tmp_dir: Path) -> None:
        processor = ImageProcessor()
        img = Image.new("RGB", (800, 600), color="blue")
        out = tmp_dir / "compressed.jpg"
        processor.compress_image(img, out)
        assert out.exists()
        reopened = Image.open(out)
        assert reopened.format == "JPEG"

    def test_compress_reduces_size(self, tmp_dir: Path) -> None:
        """Compressed JPEG should generally be smaller than a raw BMP."""
        processor = ImageProcessor()
        img = Image.new("RGB", (1920, 1080), color="blue")
        bmp_path = tmp_dir / "raw.bmp"
        img.save(bmp_path, format="BMP")
        jpg_path = tmp_dir / "compressed.jpg"
        processor.compress_image(img, jpg_path)
        assert jpg_path.stat().st_size < bmp_path.stat().st_size

    def test_strip_metadata(self, tmp_dir: Path) -> None:
        """After stripping, the image should have no EXIF data."""
        processor = ImageProcessor()
        # Create image with some EXIF-like content (PIL's new() has none,
        # but strip_metadata should still work).
        img = Image.new("RGB", (800, 600))
        clean = processor.strip_metadata(img)
        # Verify the returned image has no EXIF
        exif = clean.getexif()
        assert len(exif) == 0

    def test_preprocess_full_pipeline(self, tmp_dir: Path) -> None:
        """Full preprocess pipeline: resize + compress + strip."""
        processor = ImageProcessor()
        # Create a large source image.
        source = _make_image(width=4000, height=3000, fmt="PNG", tmp_dir=tmp_dir)
        out = tmp_dir / "processed.jpg"
        result = processor.preprocess(source, out)
        assert result == out
        assert out.exists()

        processed = Image.open(out)
        assert processed.size[0] <= processor.MAX_WIDTH
        assert processed.size[1] <= processor.MAX_HEIGHT
        assert processed.format == "JPEG"

    def test_preprocess_default_output(self, tmp_dir: Path) -> None:
        """When no output_path is given, the result should have .jpg extension."""
        processor = ImageProcessor()
        source = _make_image(width=800, height=600, fmt="PNG", tmp_dir=tmp_dir)
        result = processor.preprocess(source)
        assert result.suffix == ".jpg"
        assert result.exists()


# ====================================================================== #
# ImageUploader (upload_handler) tests
# ====================================================================== #


class TestImageUploader:
    """Test the upload handler orchestration."""

    @pytest.mark.asyncio
    async def test_validate_file_accepts_jpeg(self) -> None:
        content = _make_image_bytes(800, 600, "JPEG")
        upload = _make_upload_file(content, "photo.jpg")
        uploader = ImageUploader()
        result = await uploader.validate_file(upload)
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_file_rejects_txt(self) -> None:
        upload = _make_upload_file(b"not an image", "file.txt", "text/plain")
        uploader = ImageUploader()
        with pytest.raises(ValidationError):
            await uploader.validate_file(upload)

    def test_extract_gps_from_exif_dict(self) -> None:
        uploader = ImageUploader()
        exif = {"gps_latitude": 14.5995, "gps_longitude": 120.9842}
        coords = uploader.extract_gps_coordinates(exif)
        assert coords is not None
        assert coords == (14.5995, 120.9842)

    def test_extract_gps_returns_none(self) -> None:
        uploader = ImageUploader()
        coords = uploader.extract_gps_coordinates({})
        assert coords is None

    def test_preprocess_image(self, tmp_dir: Path) -> None:
        uploader = ImageUploader(upload_dir=tmp_dir)
        source = _make_image(width=4000, height=3000, fmt="JPEG", tmp_dir=tmp_dir)
        result = uploader.preprocess_image(source)
        assert result.exists()
        img = Image.open(result)
        assert img.size[0] <= ImageProcessor.MAX_WIDTH
        assert img.size[1] <= ImageProcessor.MAX_HEIGHT

    @pytest.mark.asyncio
    async def test_handle_upload_full(self, tmp_dir: Path) -> None:
        """End-to-end upload handler test."""
        content = _make_image_bytes(1024, 768, "JPEG")
        upload = _make_upload_file(content, "street_photo.jpg")
        user_id = uuid4()

        uploader = ImageUploader(upload_dir=tmp_dir)
        result = await uploader.handle_upload(upload, user_id)

        assert result["user_id"] == str(user_id)
        assert result["upload_id"]  # non-empty UUID string
        assert Path(result["original_path"]).exists()
        assert Path(result["processed_path"]).exists()
        assert isinstance(result["exif"], dict)

    @pytest.mark.asyncio
    async def test_handle_upload_invalid_file_rejected(self, tmp_dir: Path) -> None:
        """Upload handler should reject an invalid file."""
        upload = _make_upload_file(b"garbage data", "bad.jpg")
        uploader = ImageUploader(upload_dir=tmp_dir)
        with pytest.raises(ValidationError):
            await uploader.handle_upload(upload, uuid4())

    @pytest.mark.asyncio
    async def test_handle_upload_with_gps_outside_mm(self, tmp_dir: Path) -> None:
        """GPS outside Metro Manila should proceed but with gps=None."""
        content = _make_image_bytes(800, 600, "JPEG")
        upload = _make_upload_file(content, "photo.jpg")
        user_id = uuid4()

        uploader = ImageUploader(upload_dir=tmp_dir)

        # Mock EXIF to return out-of-bounds GPS
        with patch.object(
            uploader.extractor,
            "extract_all",
            return_value={
                "gps_latitude": 10.0,
                "gps_longitude": 125.0,
            },
        ):
            result = await uploader.handle_upload(upload, user_id)

        # Coordinates should be dropped because they're outside MM
        assert result["gps_coordinates"] is None
