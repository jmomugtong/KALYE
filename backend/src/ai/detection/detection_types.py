"""Data types for object detection results."""

from dataclasses import dataclass


@dataclass
class DetectionResult:
    """Represents a single object detection result from the YOLO pipeline.

    Attributes:
        detection_type: Category name of the detected object
            (e.g. 'pothole', 'sidewalk_obstruction', 'missing_ramp').
        confidence: Model confidence score in the range [0.0, 1.0].
        bounding_box: Bounding box coordinates as a dict with keys
            'x', 'y', 'width', 'height' (pixel units, top-left origin).
        class_id: Integer class index from the YOLO model output.
        inference_time_ms: Wall-clock inference time in milliseconds for
            the image that produced this detection.
    """

    detection_type: str
    confidence: float
    bounding_box: dict  # {"x": float, "y": float, "width": float, "height": float}
    class_id: int
    inference_time_ms: float
