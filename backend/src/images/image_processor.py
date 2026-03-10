"""Image preprocessing for the KALYE upload pipeline."""

from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)


class ImageProcessor:
    """Preprocess uploaded images before storage and AI inference.

    Operations:
        - Resize to fit within 1920x1080 while maintaining aspect ratio
        - Compress as JPEG at quality 85
        - Strip unnecessary EXIF metadata for privacy
    """

    MAX_WIDTH: int = 1920
    MAX_HEIGHT: int = 1080
    JPEG_QUALITY: int = 85

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def preprocess(self, file_path: Path, output_path: Path | None = None) -> Path:
        """Run the full preprocessing pipeline and write the result.

        Parameters
        ----------
        file_path:
            Path to the source image.
        output_path:
            Where to write the processed image.  Defaults to overwriting
            ``file_path`` with a ``.jpg`` extension.

        Returns
        -------
        Path
            The path to the processed image file.
        """
        if output_path is None:
            output_path = file_path.with_suffix(".jpg")

        image = Image.open(file_path)

        # Convert palette / RGBA images to RGB for JPEG compatibility.
        if image.mode in ("RGBA", "P", "LA"):
            image = image.convert("RGB")

        image = self.resize_image(image)
        image = self.strip_metadata(image)
        self.compress_image(image, output_path)

        logger.info("Preprocessed image saved to %s", output_path)
        return output_path

    def resize_image(self, image: Image.Image) -> Image.Image:
        """Resize the image so it fits within MAX_WIDTH x MAX_HEIGHT.

        The aspect ratio is preserved.  If the image is already within
        bounds it is returned unchanged.
        """
        width, height = image.size

        if width <= self.MAX_WIDTH and height <= self.MAX_HEIGHT:
            logger.debug("Image %dx%d is already within bounds.", width, height)
            return image

        ratio = min(self.MAX_WIDTH / width, self.MAX_HEIGHT / height)
        new_width = int(width * ratio)
        new_height = int(height * ratio)

        resized = image.resize((new_width, new_height), Image.LANCZOS)
        logger.debug("Resized image from %dx%d to %dx%d", width, height, new_width, new_height)
        return resized

    def compress_image(self, image: Image.Image, output_path: Path) -> None:
        """Save the image as JPEG with the configured quality level."""
        # Ensure RGB mode for JPEG
        if image.mode != "RGB":
            image = image.convert("RGB")

        image.save(output_path, format="JPEG", quality=self.JPEG_QUALITY, optimize=True)
        logger.debug("Compressed image saved to %s (quality=%d)", output_path, self.JPEG_QUALITY)

    @staticmethod
    def strip_metadata(image: Image.Image) -> Image.Image:
        """Return a copy of the image with all EXIF / metadata removed.

        This is important for privacy (faces, license plates may be
        referenced in EXIF thumbnails, GPS data, etc.).
        """
        data = BytesIO()
        # Save without exif and re-open to get a clean image.
        fmt = image.format or "JPEG"
        if image.mode in ("RGBA", "P", "LA") and fmt == "JPEG":
            image = image.convert("RGB")
        image.save(data, format=fmt)
        data.seek(0)
        clean = Image.open(data)
        clean.load()
        logger.debug("Stripped metadata from image.")
        return clean
