"""BLIP-2 image captioning pipeline for walkability scene descriptions."""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import torch
from PIL import Image

logger = logging.getLogger(__name__)

# Timeout in seconds for a single caption generation call.
CAPTION_TIMEOUT_SECONDS = 10


class _CaptionTimeoutError(Exception):
    """Raised when caption generation exceeds the allowed time budget."""


class BLIPCaptioner:
    """Thread-safe BLIP-2 captioner with GPU acceleration and CPU fallback.

    Parameters:
        model_name: Hugging Face model identifier for BLIP-2.
        device: ``"cuda"`` or ``"cpu"``.  When ``None`` the best available
            device is selected automatically.
    """

    def __init__(
        self,
        model_name: str = "Salesforce/blip2-opt-2.7b",
        device: Optional[str] = None,
    ) -> None:
        self.model_name = model_name
        self._processor: Any | None = None
        self._model: Any | None = None
        self._lock = threading.Lock()

        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        logger.info(
            "BLIPCaptioner configured: model_name=%s, device=%s",
            self.model_name,
            self.device,
        )

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def _load_model(self) -> None:
        """Lazily load the BLIP-2 model and processor (thread-safe)."""
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from transformers import Blip2ForConditionalGeneration, Blip2Processor

                    logger.info("Loading BLIP-2 processor from %s", self.model_name)
                    self._processor = Blip2Processor.from_pretrained(self.model_name, revision="main")  # nosec B615

                    logger.info("Loading BLIP-2 model from %s", self.model_name)
                    dtype = torch.float16 if self.device == "cuda" else torch.float32
                    self._model = Blip2ForConditionalGeneration.from_pretrained(  # nosec B615
                        self.model_name,
                        torch_dtype=dtype,
                        revision="main",
                    ).to(self.device)

                    logger.info("BLIP-2 model loaded successfully on %s", self.device)

    # ------------------------------------------------------------------
    # Preprocessing
    # ------------------------------------------------------------------

    def _preprocess_image(self, image: Image.Image) -> Dict[str, Any]:
        """Convert a PIL Image into model-ready tensors.

        Args:
            image: An RGB PIL Image.

        Returns:
            Dictionary of tensors suitable for ``model.generate()``.
        """
        self._load_model()
        inputs = self._processor(images=image, return_tensors="pt").to(self.device)
        return inputs

    # ------------------------------------------------------------------
    # Caption cleaning
    # ------------------------------------------------------------------

    @staticmethod
    def _clean_caption(caption: str) -> str:
        """Basic post-processing: strip whitespace and ensure sentence casing."""
        caption = caption.strip()
        if caption and caption[0].islower():
            caption = caption[0].upper() + caption[1:]
        if caption and not caption.endswith("."):
            caption += "."
        return caption

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_caption(
        self,
        image_path: Path,
        prompt: Optional[str] = None,
    ) -> str:
        """Generate a natural-language caption for a single image.

        Args:
            image_path: Filesystem path to the image file.
            prompt: Optional text prompt for conditional captioning
                (e.g. ``"Question: What pedestrian hazards are visible?"``).

        Returns:
            A cleaned caption string.

        Raises:
            FileNotFoundError: If *image_path* does not exist.
            TimeoutError: If generation exceeds ``CAPTION_TIMEOUT_SECONDS``.
        """
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        self._load_model()

        image = Image.open(image_path).convert("RGB")

        # Build processor inputs, optionally including a text prompt.
        if prompt is not None:
            inputs = self._processor(
                images=image, text=prompt, return_tensors="pt"
            ).to(self.device)
        else:
            inputs = self._preprocess_image(image)

        start = time.perf_counter()

        # Run generation in a worker thread so we can enforce a wall-clock
        # timeout without relying on OS signals (which only work on the main
        # thread on some platforms).
        result_container: List[str] = []
        error_container: List[Exception] = []

        def _generate() -> None:
            try:
                with torch.no_grad():
                    generated_ids = self._model.generate(
                        **inputs,
                        max_new_tokens=50,
                    )
                caption = self._processor.batch_decode(
                    generated_ids, skip_special_tokens=True
                )[0]
                result_container.append(caption)
            except Exception as exc:
                error_container.append(exc)

        worker = threading.Thread(target=_generate, daemon=True)
        worker.start()
        worker.join(timeout=CAPTION_TIMEOUT_SECONDS)

        elapsed_ms = (time.perf_counter() - start) * 1000

        if worker.is_alive():
            logger.error(
                "Caption generation timed out after %.1f ms for %s",
                elapsed_ms,
                image_path.name,
            )
            raise TimeoutError(
                f"Caption generation exceeded {CAPTION_TIMEOUT_SECONDS}s timeout"
            )

        if error_container:
            raise error_container[0]

        raw_caption = result_container[0]
        caption = self._clean_caption(raw_caption)

        logger.info(
            "Caption for %s generated in %.1f ms: %s",
            image_path.name,
            elapsed_ms,
            caption,
        )
        return caption

    def generate_captions_batch(self, image_paths: List[Path]) -> List[str]:
        """Generate captions for multiple images sequentially.

        Args:
            image_paths: List of filesystem paths to image files.

        Returns:
            List of caption strings, one per input image.
        """
        captions: List[str] = []
        for path in image_paths:
            captions.append(self.generate_caption(path))
        return captions
