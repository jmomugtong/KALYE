"""Data structures for SegFormer segmentation pipeline results."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class SegmentationResult:
    """Container for a single image segmentation inference result.

    Attributes:
        mask: 2-D list (H x W) of integer class IDs.  Stored as a plain
            Python list so it is JSON-serializable without extra conversion.
        class_labels: Ordered list of human-readable class names that
            correspond to the integer IDs in *mask*.
        class_counts: Mapping from class name to total pixel count for
            that class in the mask.
        sidewalk_coverage: Fraction of the image area classified as
            sidewalk (0.0 -- 1.0).
        inference_time_ms: Wall-clock inference time in milliseconds.
    """

    mask: list
    class_labels: List[str]
    class_counts: Dict[str, int] = field(default_factory=dict)
    sidewalk_coverage: float = 0.0
    inference_time_ms: float = 0.0
