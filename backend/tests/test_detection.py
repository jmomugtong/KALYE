"""Unit tests for the YOLOv8 detection pipeline."""

from __future__ import annotations

from dataclasses import fields
from pathlib import Path
from typing import List
from unittest.mock import MagicMock, patch

import pytest

from src.ai.detection.detection_types import DetectionResult
from src.ai.detection.postprocessor import DetectionPostprocessor
from src.ai.detection.yolo_detector import CLASS_ID_TO_NAME, YOLODetector


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_detection(
    detection_type: str = "pothole",
    confidence: float = 0.85,
    x: float = 10.0,
    y: float = 20.0,
    width: float = 50.0,
    height: float = 40.0,
    class_id: int = 0,
    inference_time_ms: float = 15.0,
) -> DetectionResult:
    return DetectionResult(
        detection_type=detection_type,
        confidence=confidence,
        bounding_box={"x": x, "y": y, "width": width, "height": height},
        class_id=class_id,
        inference_time_ms=inference_time_ms,
    )


def _build_mock_yolo_result(
    boxes_data: List[dict],
) -> MagicMock:
    """Create a mock that mimics ultralytics YOLO result structure.

    Each entry in *boxes_data* should have keys:
        xyxy (list[float]), cls (int), conf (float).
    """
    import torch

    mock_boxes = MagicMock()
    n = len(boxes_data)

    if n == 0:
        mock_boxes.__len__ = lambda self: 0  # noqa: ARG005
        mock_boxes.xyxy = torch.empty(0, 4)
        mock_boxes.cls = torch.empty(0)
        mock_boxes.conf = torch.empty(0)
    else:
        mock_boxes.__len__ = lambda self: n  # noqa: ARG005
        mock_boxes.xyxy = torch.tensor([b["xyxy"] for b in boxes_data])
        mock_boxes.cls = torch.tensor([b["cls"] for b in boxes_data], dtype=torch.float32)
        mock_boxes.conf = torch.tensor([b["conf"] for b in boxes_data])

    mock_result = MagicMock()
    mock_result.boxes = mock_boxes
    return mock_result


# ---------------------------------------------------------------------------
# DetectionResult dataclass tests
# ---------------------------------------------------------------------------

class TestDetectionResult:
    def test_dataclass_fields(self):
        """DetectionResult has exactly the expected fields."""
        field_names = {f.name for f in fields(DetectionResult)}
        assert field_names == {
            "detection_type",
            "confidence",
            "bounding_box",
            "class_id",
            "inference_time_ms",
        }

    def test_creation(self):
        det = _make_detection()
        assert det.detection_type == "pothole"
        assert det.confidence == 0.85
        assert det.bounding_box == {"x": 10.0, "y": 20.0, "width": 50.0, "height": 40.0}
        assert det.class_id == 0
        assert det.inference_time_ms == 15.0


# ---------------------------------------------------------------------------
# YOLODetector tests
# ---------------------------------------------------------------------------

class TestYOLODetectorInit:
    def test_default_threshold(self):
        detector = YOLODetector()
        assert detector.confidence_threshold == 0.70

    def test_custom_threshold(self):
        detector = YOLODetector(confidence_threshold=0.50)
        assert detector.confidence_threshold == 0.50

    def test_default_model_path(self):
        detector = YOLODetector()
        assert detector.model_path == "yolov8n.pt"

    def test_custom_model_path(self):
        detector = YOLODetector(model_path="/models/custom.pt")
        assert detector.model_path == "/models/custom.pt"


class TestYOLODetectorDetect:
    @patch("src.ai.detection.yolo_detector.YOLODetector._load_model")
    def test_single_image_returns_detection_list(self, mock_load, tmp_path):
        """detect() returns a list of DetectionResult objects."""
        img = tmp_path / "test.jpg"
        img.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

        mock_model = MagicMock()
        mock_result = _build_mock_yolo_result([
            {"xyxy": [10.0, 20.0, 60.0, 60.0], "cls": 0, "conf": 0.92},
        ])
        mock_model.return_value = [mock_result]
        mock_load.return_value = mock_model

        detector = YOLODetector()
        results = detector.detect(img)

        assert isinstance(results, list)
        assert len(results) == 1
        assert isinstance(results[0], DetectionResult)
        assert results[0].detection_type == "pothole"

    @patch("src.ai.detection.yolo_detector.YOLODetector._load_model")
    def test_confidence_filtering(self, mock_load, tmp_path):
        """Detections below threshold are removed."""
        img = tmp_path / "test.jpg"
        img.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

        mock_model = MagicMock()
        mock_result = _build_mock_yolo_result([
            {"xyxy": [0, 0, 50, 50], "cls": 0, "conf": 0.90},
            {"xyxy": [60, 60, 100, 100], "cls": 1, "conf": 0.50},  # below 0.70
        ])
        mock_model.return_value = [mock_result]
        mock_load.return_value = mock_model

        detector = YOLODetector(confidence_threshold=0.70)
        results = detector.detect(img)

        assert len(results) == 1
        assert results[0].confidence >= 0.70

    @patch("src.ai.detection.yolo_detector.YOLODetector._load_model")
    def test_bounding_box_format(self, mock_load, tmp_path):
        """Bounding boxes are expressed as {x, y, width, height}."""
        img = tmp_path / "test.jpg"
        img.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

        mock_model = MagicMock()
        mock_result = _build_mock_yolo_result([
            {"xyxy": [10.0, 20.0, 60.0, 80.0], "cls": 0, "conf": 0.95},
        ])
        mock_model.return_value = [mock_result]
        mock_load.return_value = mock_model

        detector = YOLODetector()
        det = detector.detect(img)[0]

        bbox = det.bounding_box
        assert set(bbox.keys()) == {"x", "y", "width", "height"}
        assert bbox["x"] == pytest.approx(10.0)
        assert bbox["y"] == pytest.approx(20.0)
        assert bbox["width"] == pytest.approx(50.0)  # 60 - 10
        assert bbox["height"] == pytest.approx(60.0)  # 80 - 20

    @patch("src.ai.detection.yolo_detector.YOLODetector._load_model")
    def test_batch_detection(self, mock_load, tmp_path):
        """detect_batch returns one result list per image."""
        images = []
        for i in range(3):
            img = tmp_path / f"img_{i}.jpg"
            img.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
            images.append(img)

        mock_model = MagicMock()
        mock_result = _build_mock_yolo_result([
            {"xyxy": [0, 0, 30, 30], "cls": 0, "conf": 0.80},
        ])
        mock_model.return_value = [mock_result]
        mock_load.return_value = mock_model

        detector = YOLODetector()
        batch_results = detector.detect_batch(images)

        assert len(batch_results) == 3
        for result_list in batch_results:
            assert isinstance(result_list, list)

    @patch("src.ai.detection.yolo_detector.YOLODetector._load_model")
    def test_empty_detections(self, mock_load, tmp_path):
        """An image with no detections returns an empty list."""
        img = tmp_path / "empty.jpg"
        img.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

        mock_model = MagicMock()
        mock_result = _build_mock_yolo_result([])
        mock_model.return_value = [mock_result]
        mock_load.return_value = mock_model

        detector = YOLODetector()
        results = detector.detect(img)

        assert results == []

    @patch("src.ai.detection.yolo_detector.YOLODetector._load_model")
    def test_inference_time_tracked(self, mock_load, tmp_path):
        """Each DetectionResult carries a positive inference_time_ms."""
        img = tmp_path / "test.jpg"
        img.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

        mock_model = MagicMock()
        mock_result = _build_mock_yolo_result([
            {"xyxy": [0, 0, 50, 50], "cls": 0, "conf": 0.85},
        ])
        mock_model.return_value = [mock_result]
        mock_load.return_value = mock_model

        detector = YOLODetector()
        results = detector.detect(img)

        assert len(results) == 1
        assert results[0].inference_time_ms > 0

    def test_missing_image_raises(self):
        """detect() raises FileNotFoundError for a nonexistent path."""
        detector = YOLODetector()
        with pytest.raises(FileNotFoundError):
            detector.detect(Path("/nonexistent/image.jpg"))


# ---------------------------------------------------------------------------
# Postprocessor tests
# ---------------------------------------------------------------------------

class TestNMS:
    def test_nms_removes_overlapping(self):
        """NMS keeps the higher-confidence detection when IoU > threshold."""
        pp = DetectionPostprocessor()

        dets = [
            _make_detection(confidence=0.95, x=10, y=10, width=50, height=50),
            _make_detection(confidence=0.80, x=12, y=12, width=50, height=50),  # overlaps a lot
        ]
        result = pp.apply_nms(dets, iou_threshold=0.5)

        assert len(result) == 1
        assert result[0].confidence == 0.95

    def test_nms_keeps_non_overlapping(self):
        """NMS keeps detections that do not overlap."""
        pp = DetectionPostprocessor()

        dets = [
            _make_detection(confidence=0.90, x=0, y=0, width=20, height=20),
            _make_detection(confidence=0.85, x=200, y=200, width=20, height=20),
        ]
        result = pp.apply_nms(dets, iou_threshold=0.5)

        assert len(result) == 2

    def test_nms_empty_input(self):
        pp = DetectionPostprocessor()
        assert pp.apply_nms([]) == []


class TestFilterSmallDetections:
    def test_removes_small(self):
        pp = DetectionPostprocessor()

        dets = [
            _make_detection(width=5, height=5),     # area = 25 -> removed
            _make_detection(width=20, height=20),    # area = 400 -> kept
        ]
        result = pp.filter_small_detections(dets, min_area=100)

        assert len(result) == 1
        assert result[0].bounding_box["width"] == 20

    def test_keeps_exact_threshold(self):
        pp = DetectionPostprocessor()
        dets = [_make_detection(width=10, height=10)]  # area = 100
        result = pp.filter_small_detections(dets, min_area=100)
        assert len(result) == 1


class TestMergeNearbyDetections:
    def test_merge_same_type_nearby(self):
        """Two nearby same-type detections merge into one."""
        pp = DetectionPostprocessor()

        dets = [
            _make_detection(detection_type="pothole", confidence=0.90, x=100, y=100, width=30, height=30),
            _make_detection(detection_type="pothole", confidence=0.80, x=120, y=110, width=30, height=30),
        ]
        result = pp.merge_nearby_detections(dets, distance_threshold=50.0)

        assert len(result) == 1
        assert result[0].confidence == 0.90  # kept best confidence

    def test_no_merge_different_types(self):
        """Different detection types are never merged."""
        pp = DetectionPostprocessor()

        dets = [
            _make_detection(detection_type="pothole", x=100, y=100, width=30, height=30),
            _make_detection(detection_type="missing_ramp", x=110, y=110, width=30, height=30),
        ]
        result = pp.merge_nearby_detections(dets, distance_threshold=50.0)

        assert len(result) == 2

    def test_no_merge_far_apart(self):
        """Same-type detections far apart are not merged."""
        pp = DetectionPostprocessor()

        dets = [
            _make_detection(detection_type="pothole", x=0, y=0, width=20, height=20),
            _make_detection(detection_type="pothole", x=500, y=500, width=20, height=20),
        ]
        result = pp.merge_nearby_detections(dets, distance_threshold=50.0)

        assert len(result) == 2

    def test_merge_expands_bbox(self):
        """Merged detection's bbox covers all cluster members."""
        pp = DetectionPostprocessor()

        dets = [
            _make_detection(detection_type="pothole", confidence=0.90, x=100, y=100, width=20, height=20),
            _make_detection(detection_type="pothole", confidence=0.80, x=110, y=105, width=20, height=20),
        ]
        result = pp.merge_nearby_detections(dets, distance_threshold=50.0)

        assert len(result) == 1
        bbox = result[0].bounding_box
        assert bbox["x"] == 100        # min x
        assert bbox["y"] == 100        # min y
        assert bbox["width"] == 30     # 130 - 100
        assert bbox["height"] == 25    # 125 - 100

    def test_merge_empty_input(self):
        pp = DetectionPostprocessor()
        assert pp.merge_nearby_detections([]) == []
