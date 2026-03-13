"""SegFormer-based semantic segmentation pipeline.

Uses the ``transformers`` library to run SegFormer inference on street
imagery.  The default model (``nvidia/segformer-b3-finetuned-ade-512-512``)
is fine-tuned on the ADE20K dataset which includes sidewalk / road /
building classes relevant to walkability analysis.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from PIL import Image

from src.ai.segmentation.segmentation_result import SegmentationResult

logger = logging.getLogger(__name__)

# ADE20K class labels (150 classes).  Index 0 = "wall", etc.
# We store only names referenced elsewhere; the full list is provided
# by the model's config and loaded at runtime.
_ADE20K_SIDEWALK_CLASS_ID = 11  # "sidewalk / pavement"


class SegFormerSegmenter:
    """Run SegFormer semantic segmentation on images.

    Parameters
    ----------
    model_name:
        Hugging Face model identifier.  Defaults to the ADE20K-finetuned
        SegFormer-B3 checkpoint.
    device:
        ``"cuda"`` or ``"cpu"``.  When *None* the best available device
        is auto-detected.
    """

    def __init__(
        self,
        model_name: str = "nvidia/segformer-b3-finetuned-ade-512-512",
        device: Optional[str] = None,
    ) -> None:
        self.model_name = model_name
        self.device = device or self._detect_device()
        self._model: Any = None
        self._processor: Any = None
        self._class_labels: List[str] = []
        logger.info(
            "SegFormerSegmenter created  model=%s  device=%s",
            self.model_name,
            self.device,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def segment(self, image_path: Path) -> SegmentationResult:
        """Run segmentation on a single image and return the result."""
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        model, processor = self._ensure_loaded()

        image = Image.open(image_path).convert("RGB")
        original_size = (image.height, image.width)

        inputs = self._preprocess_image(image)

        start = time.perf_counter()
        outputs = self._run_inference(model, inputs)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        mask_np = self._postprocess_mask(outputs.logits, original_size)

        # Build class counts
        class_counts = self._compute_class_counts(mask_np)

        # Sidewalk coverage
        total_pixels = mask_np.size
        sidewalk_pixels = class_counts.get(
            self._label_for_id(_ADE20K_SIDEWALK_CLASS_ID), 0
        )
        sidewalk_coverage = sidewalk_pixels / total_pixels if total_pixels > 0 else 0.0

        return SegmentationResult(
            mask=mask_np.tolist(),
            class_labels=list(self._class_labels),
            class_counts=class_counts,
            sidewalk_coverage=sidewalk_coverage,
            inference_time_ms=elapsed_ms,
        )

    def segment_batch(self, image_paths: List[Path]) -> List[SegmentationResult]:
        """Segment multiple images sequentially.

        A future optimisation could batch images on the GPU; for now we
        iterate to keep memory pressure predictable.
        """
        results: List[SegmentationResult] = []
        for path in image_paths:
            results.append(self.segment(path))
        return results

    # ------------------------------------------------------------------
    # Preprocessing / Postprocessing
    # ------------------------------------------------------------------

    def _preprocess_image(self, image: Image.Image) -> Dict[str, Any]:
        """Prepare a PIL image for SegFormer inference.

        Uses ``SegformerImageProcessor`` which handles resizing to
        512x512 and normalisation.
        """
        _, processor = self._ensure_loaded()
        inputs = processor(images=image, return_tensors="pt")

        if self.device == "cuda":
            import torch  # noqa: F811

            inputs = {k: v.to(self.device) for k, v in inputs.items()}

        return inputs

    def _postprocess_mask(self, logits: Any, original_size: tuple) -> np.ndarray:
        """Convert raw model logits to an (H, W) integer class-ID mask.

        The logits tensor has shape ``(1, num_classes, h, w)`` at the
        model's internal resolution.  We upsample to *original_size*
        and take the argmax.

        Parameters
        ----------
        logits:
            Raw model output logits (torch.Tensor).
        original_size:
            ``(height, width)`` of the original input image.
        """
        import torch
        import torch.nn.functional as F

        # logits shape: (batch, num_classes, h, w)
        upsampled = F.interpolate(
            logits,
            size=original_size,
            mode="bilinear",
            align_corners=False,
        )
        mask = upsampled.argmax(dim=1).squeeze(0)  # (H, W)
        return mask.cpu().numpy().astype(np.int32)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> tuple:
        """Lazy-load the model and processor on first use."""
        if self._model is None or self._processor is None:
            self._load_model()
        return self._model, self._processor

    def _load_model(self) -> None:
        """Download (if needed) and load the SegFormer model + processor."""
        from transformers import (
            SegformerForSemanticSegmentation,
            SegformerImageProcessor,
        )

        logger.info("Loading SegFormer model: %s", self.model_name)
        self._processor = SegformerImageProcessor.from_pretrained(self.model_name, revision="main")  # nosec B615
        self._model = SegformerForSemanticSegmentation.from_pretrained(self.model_name, revision="main")  # nosec B615

        # Move to device
        if self.device == "cuda":
            try:
                self._model = self._model.to(self.device)
            except Exception:
                logger.warning(
                    "Failed to move model to CUDA -- falling back to CPU"
                )
                self.device = "cpu"
                self._model = self._model.to("cpu")
        else:
            self._model = self._model.to("cpu")

        self._model.eval()

        # Populate class labels from model config
        id2label = getattr(self._model.config, "id2label", {})
        if id2label:
            max_id = max(int(k) for k in id2label.keys())
            self._class_labels = [
                id2label.get(i, id2label.get(str(i), f"class_{i}"))
                for i in range(max_id + 1)
            ]
        else:
            self._class_labels = []

        logger.info(
            "SegFormer loaded  classes=%d  device=%s",
            len(self._class_labels),
            self.device,
        )

    def _run_inference(self, model: Any, inputs: Dict[str, Any]) -> Any:
        """Forward pass through the model with no-grad context."""
        import torch

        with torch.no_grad():
            outputs = model(**inputs)
        return outputs

    def _compute_class_counts(self, mask: np.ndarray) -> Dict[str, int]:
        """Count pixels per class in *mask* and return {label: count}."""
        unique, counts = np.unique(mask, return_counts=True)
        result: Dict[str, int] = {}
        for class_id, count in zip(unique, counts):
            label = self._label_for_id(int(class_id))
            result[label] = int(count)
        return result

    def _label_for_id(self, class_id: int) -> str:
        if 0 <= class_id < len(self._class_labels):
            return self._class_labels[class_id]
        return f"class_{class_id}"

    # ------------------------------------------------------------------
    # Device detection
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_device() -> str:
        """Auto-detect the best available device."""
        try:
            import torch

            if torch.cuda.is_available():
                return "cuda"
        except ImportError:
            logger.debug("torch not installed -- defaulting to cpu")
        return "cpu"
