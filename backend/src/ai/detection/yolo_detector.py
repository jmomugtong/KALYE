"""YOLOv8-based object detector for walkability infrastructure issues."""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any, List

from src.ai.detection.detection_types import DetectionResult

logger = logging.getLogger(__name__)

# Mapping from YOLO class IDs to human-readable detection type names.
# This should be updated to match the trained model's class list.
CLASS_ID_TO_NAME: dict[int, str] = {
    0: "pothole",
    1: "sidewalk_obstruction",
    2: "missing_ramp",
    3: "broken_sidewalk",
    4: "illegal_parking",
    5: "street_vendor_obstruction",
    6: "utility_pole_obstruction",
    7: "flooding",
    8: "missing_tactile_paving",
    9: "damaged_signage",
}


class YOLODetector:
    """Thread-safe YOLOv8 detector with configurable confidence threshold.

    Parameters:
        model_path: Path to a YOLO model weights file (.pt). When ``None``
            the default ``yolov8n.pt`` pretrained checkpoint is used.
        confidence_threshold: Minimum confidence score to keep a detection.
            Defaults to 0.70 per project spec.
    """

    def __init__(
        self,
        model_path: str | None = None,
        confidence_threshold: float = 0.70,
    ) -> None:
        self.model_path = model_path or "yolov8n.pt"
        self.confidence_threshold = confidence_threshold
        self._model: Any | None = None
        self._lock = threading.Lock()

        logger.info(
            "YOLODetector configured: model_path=%s, confidence_threshold=%.2f",
            self.model_path,
            self.confidence_threshold,
        )

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def _load_model(self) -> Any:
        """Lazily load the YOLO model in a thread-safe manner."""
        if self._model is None:
            with self._lock:
                # Double-checked locking
                if self._model is None:
                    from ultralytics import YOLO

                    logger.info("Loading YOLO model from %s", self.model_path)
                    self._model = YOLO(self.model_path)
                    logger.info("YOLO model loaded successfully")
        return self._model

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(self, image_path: Path) -> List[DetectionResult]:
        """Run detection on a single image.

        Args:
            image_path: Filesystem path to the image file.

        Returns:
            List of ``DetectionResult`` instances that pass the confidence
            threshold.

        Raises:
            FileNotFoundError: If *image_path* does not exist.
            ValueError: If the file cannot be decoded as an image.
        """
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        model = self._load_model()

        start = time.perf_counter()
        try:
            results = model(str(image_path), verbose=False)
        except Exception as exc:
            raise ValueError(f"Failed to process image {image_path}: {exc}") from exc
        elapsed_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "Inference on %s completed in %.1f ms",
            image_path.name,
            elapsed_ms,
        )

        detections = self._postprocess_results(results, elapsed_ms)
        return self._filter_by_confidence(detections)

    def detect_batch(self, image_paths: List[Path]) -> List[List[DetectionResult]]:
        """Run detection on multiple images sequentially.

        Args:
            image_paths: List of filesystem paths to image files.

        Returns:
            A list whose *i*-th element is the detection list for the
            *i*-th image.
        """
        return [self.detect(p) for p in image_paths]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _postprocess_results(
        self,
        results: Any,
        inference_time_ms: float = 0.0,
    ) -> List[DetectionResult]:
        """Convert raw YOLO output into ``DetectionResult`` instances.

        Args:
            results: The list-like object returned by ``model()``.
            inference_time_ms: Elapsed wall-clock time for the inference
                call, propagated into every ``DetectionResult``.

        Returns:
            Unfiltered list of detections.
        """
        detections: List[DetectionResult] = []

        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue

            for i in range(len(boxes)):
                # xyxy -> x, y, w, h
                xyxy = boxes.xyxy[i].tolist()
                x1, y1, x2, y2 = xyxy[0], xyxy[1], xyxy[2], xyxy[3]
                width = x2 - x1
                height = y2 - y1

                class_id = int(boxes.cls[i].item())
                confidence = float(boxes.conf[i].item())

                detection_type = CLASS_ID_TO_NAME.get(class_id, f"unknown_{class_id}")

                detections.append(
                    DetectionResult(
                        detection_type=detection_type,
                        confidence=confidence,
                        bounding_box={
                            "x": x1,
                            "y": y1,
                            "width": width,
                            "height": height,
                        },
                        class_id=class_id,
                        inference_time_ms=inference_time_ms,
                    )
                )

        return detections

    def _filter_by_confidence(
        self,
        detections: List[DetectionResult],
    ) -> List[DetectionResult]:
        """Keep only detections whose confidence meets the threshold."""
        filtered = [d for d in detections if d.confidence >= self.confidence_threshold]
        if len(filtered) < len(detections):
            logger.debug(
                "Confidence filter: kept %d / %d detections (threshold=%.2f)",
                len(filtered),
                len(detections),
                self.confidence_threshold,
            )
        return filtered
