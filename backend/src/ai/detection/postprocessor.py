"""Post-processing utilities for object detection results."""

from __future__ import annotations

import logging
import math
from typing import List

from src.ai.detection.detection_types import DetectionResult

logger = logging.getLogger(__name__)


class DetectionPostprocessor:
    """Collection of post-processing operations on detection results.

    All methods are stateless and can be used as static helpers, but are
    kept as instance methods so the class can be extended with configuration
    in the future.
    """

    # ------------------------------------------------------------------
    # Non-Maximum Suppression
    # ------------------------------------------------------------------

    def apply_nms(
        self,
        detections: List[DetectionResult],
        iou_threshold: float = 0.5,
    ) -> List[DetectionResult]:
        """Remove overlapping detections via greedy Non-Maximum Suppression.

        Detections are sorted by confidence (descending).  For each kept
        detection, all remaining detections with an IoU above
        *iou_threshold* are suppressed.

        Args:
            detections: Input detection list.
            iou_threshold: IoU above which the lower-confidence detection
                is suppressed.

        Returns:
            Filtered list of detections.
        """
        if not detections:
            return []

        sorted_dets = sorted(detections, key=lambda d: d.confidence, reverse=True)
        kept: List[DetectionResult] = []

        while sorted_dets:
            best = sorted_dets.pop(0)
            kept.append(best)
            sorted_dets = [
                d
                for d in sorted_dets
                if self._compute_iou(best.bounding_box, d.bounding_box) < iou_threshold
            ]

        logger.debug("NMS: %d -> %d detections (iou_threshold=%.2f)", len(detections), len(kept), iou_threshold)
        return kept

    # ------------------------------------------------------------------
    # Small detection filter
    # ------------------------------------------------------------------

    def filter_small_detections(
        self,
        detections: List[DetectionResult],
        min_area: int = 100,
    ) -> List[DetectionResult]:
        """Remove detections whose bounding box area is below *min_area*.

        Args:
            detections: Input detection list.
            min_area: Minimum area in square pixels.

        Returns:
            Filtered list of detections.
        """
        filtered = [
            d
            for d in detections
            if d.bounding_box["width"] * d.bounding_box["height"] >= min_area
        ]
        logger.debug(
            "Small-detection filter: %d -> %d (min_area=%d)",
            len(detections),
            len(filtered),
            min_area,
        )
        return filtered

    # ------------------------------------------------------------------
    # Merge nearby detections
    # ------------------------------------------------------------------

    def merge_nearby_detections(
        self,
        detections: List[DetectionResult],
        distance_threshold: float = 50.0,
    ) -> List[DetectionResult]:
        """Merge detections of the same type whose centres are close.

        For each cluster of same-type detections within
        *distance_threshold* pixels, the detection with the highest
        confidence is kept and its bounding box is expanded to cover all
        merged detections.

        Args:
            detections: Input detection list.
            distance_threshold: Maximum Euclidean distance (in pixels)
                between bounding-box centres to consider merging.

        Returns:
            Merged list of detections.
        """
        if not detections:
            return []

        used = [False] * len(detections)
        merged: List[DetectionResult] = []

        for i, det_i in enumerate(detections):
            if used[i]:
                continue

            cluster = [det_i]
            used[i] = True
            cx_i, cy_i = self._centre(det_i.bounding_box)

            for j in range(i + 1, len(detections)):
                if used[j]:
                    continue
                det_j = detections[j]
                if det_j.detection_type != det_i.detection_type:
                    continue
                cx_j, cy_j = self._centre(det_j.bounding_box)
                dist = math.hypot(cx_i - cx_j, cy_i - cy_j)
                if dist <= distance_threshold:
                    cluster.append(det_j)
                    used[j] = True

            # Keep highest-confidence detection, but expand bbox
            best = max(cluster, key=lambda d: d.confidence)
            if len(cluster) > 1:
                best = self._expand_bbox(best, cluster)

            merged.append(best)

        logger.debug(
            "Merge nearby: %d -> %d (distance_threshold=%.1f)",
            len(detections),
            len(merged),
            distance_threshold,
        )
        return merged

    # ------------------------------------------------------------------
    # Geometry helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _centre(bbox: dict) -> tuple[float, float]:
        """Return the centre (cx, cy) of a bounding box dict."""
        return (
            bbox["x"] + bbox["width"] / 2.0,
            bbox["y"] + bbox["height"] / 2.0,
        )

    @staticmethod
    def _compute_iou(box_a: dict, box_b: dict) -> float:
        """Compute Intersection-over-Union for two bounding box dicts."""
        ax1, ay1 = box_a["x"], box_a["y"]
        ax2, ay2 = ax1 + box_a["width"], ay1 + box_a["height"]

        bx1, by1 = box_b["x"], box_b["y"]
        bx2, by2 = bx1 + box_b["width"], by1 + box_b["height"]

        inter_x1 = max(ax1, bx1)
        inter_y1 = max(ay1, by1)
        inter_x2 = min(ax2, bx2)
        inter_y2 = min(ay2, by2)

        inter_area = max(0.0, inter_x2 - inter_x1) * max(0.0, inter_y2 - inter_y1)

        area_a = box_a["width"] * box_a["height"]
        area_b = box_b["width"] * box_b["height"]
        union_area = area_a + area_b - inter_area

        if union_area <= 0:
            return 0.0
        return inter_area / union_area

    @staticmethod
    def _expand_bbox(
        best: DetectionResult,
        cluster: List[DetectionResult],
    ) -> DetectionResult:
        """Return a new DetectionResult with a bbox covering all cluster members."""
        min_x = min(d.bounding_box["x"] for d in cluster)
        min_y = min(d.bounding_box["y"] for d in cluster)
        max_x = max(d.bounding_box["x"] + d.bounding_box["width"] for d in cluster)
        max_y = max(d.bounding_box["y"] + d.bounding_box["height"] for d in cluster)

        return DetectionResult(
            detection_type=best.detection_type,
            confidence=best.confidence,
            bounding_box={
                "x": min_x,
                "y": min_y,
                "width": max_x - min_x,
                "height": max_y - min_y,
            },
            class_id=best.class_id,
            inference_time_ms=best.inference_time_ms,
        )
