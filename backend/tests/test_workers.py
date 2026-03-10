"""Tests for Celery worker tasks and progress tracking."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from src.ai.detection.detection_types import DetectionResult
from src.ai.segmentation.segmentation_result import SegmentationResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_redis():
    """In-memory dict-backed mock Redis client."""
    store: Dict[str, str] = {}

    client = MagicMock()
    client.setex = MagicMock(
        side_effect=lambda key, ttl, value: store.__setitem__(key, value)
    )
    client.get = MagicMock(side_effect=lambda key: store.get(key))
    client._store = store
    return client


@pytest.fixture
def sample_detection() -> DetectionResult:
    return DetectionResult(
        detection_type="pothole",
        confidence=0.92,
        bounding_box={"x": 10.0, "y": 20.0, "width": 50.0, "height": 40.0},
        class_id=0,
        inference_time_ms=15.0,
    )


@pytest.fixture
def sample_segmentation_result() -> SegmentationResult:
    return SegmentationResult(
        mask=[[0, 1], [1, 0]],
        class_labels=["road", "sidewalk"],
        class_counts={"road": 2, "sidewalk": 2},
        sidewalk_coverage=0.50,
        inference_time_ms=45.0,
    )


# ---------------------------------------------------------------------------
# Celery app configuration tests
# ---------------------------------------------------------------------------

class TestCeleryAppConfig:
    def test_celery_app_exists(self):
        from src.workers.celery_app import celery_app

        assert celery_app is not None
        assert celery_app.main == "kalye"

    def test_celery_serializer_is_json(self):
        from src.workers.celery_app import celery_app

        assert celery_app.conf.task_serializer == "json"
        assert celery_app.conf.result_serializer == "json"

    def test_celery_timezone(self):
        from src.workers.celery_app import celery_app

        assert celery_app.conf.timezone == "Asia/Manila"

    def test_celery_task_routes(self):
        from src.workers.celery_app import celery_app

        routes = celery_app.conf.task_routes
        assert "src.workers.tasks.detection.*" in routes
        assert "src.workers.tasks.segmentation.*" in routes
        assert "src.workers.tasks.captioning.*" in routes
        assert routes["src.workers.tasks.detection.*"] == {"queue": "detection"}

    def test_celery_task_tracking_enabled(self):
        from src.workers.celery_app import celery_app

        assert celery_app.conf.task_track_started is True
        assert celery_app.conf.task_acks_late is True


# ---------------------------------------------------------------------------
# Detection task tests
# ---------------------------------------------------------------------------

class TestDetectionTask:
    @patch("src.workers.tasks.detection.YOLODetector")
    def test_run_yolo_detection_success(self, MockDetector, sample_detection):
        """Detection task returns list of detection dicts."""
        mock_instance = MagicMock()
        mock_instance.detect.return_value = [sample_detection]
        MockDetector.return_value = mock_instance

        from src.workers.tasks.detection import run_yolo_detection

        # Use .apply() to run synchronously in-process (eager mode)
        result = run_yolo_detection.apply(
            args=["img-001", "/tmp/test.jpg"]
        ).get()

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["detection_type"] == "pothole"
        assert result[0]["confidence"] == 0.92
        mock_instance.detect.assert_called_once()

    @patch("src.workers.tasks.detection.YOLODetector")
    def test_run_yolo_detection_empty(self, MockDetector):
        """Detection task returns empty list when no detections found."""
        mock_instance = MagicMock()
        mock_instance.detect.return_value = []
        MockDetector.return_value = mock_instance

        from src.workers.tasks.detection import run_yolo_detection

        result = run_yolo_detection.apply(
            args=["img-002", "/tmp/empty.jpg"]
        ).get()

        assert result == []

    @patch("src.workers.tasks.detection.YOLODetector")
    def test_run_yolo_detection_file_not_found(self, MockDetector):
        """Detection task raises when image file is missing."""
        mock_instance = MagicMock()
        mock_instance.detect.side_effect = FileNotFoundError("not found")
        MockDetector.return_value = mock_instance

        from src.workers.tasks.detection import run_yolo_detection

        with pytest.raises(FileNotFoundError):
            run_yolo_detection.apply(
                args=["img-003", "/tmp/missing.jpg"]
            ).get()


# ---------------------------------------------------------------------------
# Segmentation task tests
# ---------------------------------------------------------------------------

class TestSegmentationTask:
    @patch("src.workers.tasks.segmentation.SegFormerSegmenter")
    def test_run_segmentation_success(self, MockSegmenter, sample_segmentation_result):
        """Segmentation task returns result dict."""
        mock_instance = MagicMock()
        mock_instance.segment.return_value = sample_segmentation_result
        MockSegmenter.return_value = mock_instance

        from src.workers.tasks.segmentation import run_segmentation

        result = run_segmentation.apply(
            args=["img-001", "/tmp/test.jpg"]
        ).get()

        assert isinstance(result, dict)
        assert result["sidewalk_coverage"] == 0.50
        assert result["class_counts"] == {"road": 2, "sidewalk": 2}
        mock_instance.segment.assert_called_once()

    @patch("src.workers.tasks.segmentation.SegFormerSegmenter")
    def test_run_segmentation_file_not_found(self, MockSegmenter):
        """Segmentation task raises when image file is missing."""
        mock_instance = MagicMock()
        mock_instance.segment.side_effect = FileNotFoundError("not found")
        MockSegmenter.return_value = mock_instance

        from src.workers.tasks.segmentation import run_segmentation

        with pytest.raises(FileNotFoundError):
            run_segmentation.apply(
                args=["img-003", "/tmp/missing.jpg"]
            ).get()


# ---------------------------------------------------------------------------
# Captioning task tests
# ---------------------------------------------------------------------------

class TestCaptioningTask:
    @patch("src.workers.tasks.captioning.BLIPCaptioner")
    def test_run_captioning_success(self, MockCaptioner):
        """Captioning task returns a caption string."""
        mock_instance = MagicMock()
        mock_instance.generate_caption.return_value = "A street with potholes and missing sidewalk."
        MockCaptioner.return_value = mock_instance

        from src.workers.tasks.captioning import run_captioning

        result = run_captioning.apply(
            args=["img-001", "/tmp/test.jpg"]
        ).get()

        assert isinstance(result, str)
        assert "pothole" in result.lower()
        mock_instance.generate_caption.assert_called_once()

    @patch("src.workers.tasks.captioning.BLIPCaptioner")
    def test_run_captioning_file_not_found(self, MockCaptioner):
        """Captioning task raises when image file is missing."""
        mock_instance = MagicMock()
        mock_instance.generate_caption.side_effect = FileNotFoundError("not found")
        MockCaptioner.return_value = mock_instance

        from src.workers.tasks.captioning import run_captioning

        with pytest.raises(FileNotFoundError):
            run_captioning.apply(
                args=["img-003", "/tmp/missing.jpg"]
            ).get()


# ---------------------------------------------------------------------------
# Image processing orchestration tests
# ---------------------------------------------------------------------------

class TestImageProcessingTask:
    @patch("src.workers.tasks.image_processing.ProgressTracker")
    @patch("src.workers.tasks.captioning.BLIPCaptioner")
    @patch("src.workers.tasks.segmentation.SegFormerSegmenter")
    @patch("src.workers.tasks.detection.YOLODetector")
    def test_process_image_success(
        self,
        MockDetector,
        MockSegmenter,
        MockCaptioner,
        MockTracker,
        sample_detection,
        sample_segmentation_result,
    ):
        """Orchestration task combines all three pipeline results."""
        # Setup detection mock
        det_instance = MagicMock()
        det_instance.detect.return_value = [sample_detection]
        MockDetector.return_value = det_instance

        # Setup segmentation mock
        seg_instance = MagicMock()
        seg_instance.segment.return_value = sample_segmentation_result
        MockSegmenter.return_value = seg_instance

        # Setup captioning mock
        cap_instance = MagicMock()
        cap_instance.generate_caption.return_value = "A damaged street."
        MockCaptioner.return_value = cap_instance

        # Setup tracker mock
        tracker_instance = MagicMock()
        MockTracker.return_value = tracker_instance

        from src.workers.tasks.image_processing import process_image_task

        result = process_image_task.apply(
            args=["img-001", "/tmp/test.jpg"]
        ).get()

        assert result["image_id"] == "img-001"
        assert result["status"] == "completed"
        assert len(result["detections"]) == 1
        assert result["segmentation"]["sidewalk_coverage"] == 0.50
        assert result["caption"] == "A damaged street."
        assert result["processing_time_ms"] > 0
        assert result["errors"] == []

    @patch("src.workers.tasks.image_processing.ProgressTracker")
    @patch("src.workers.tasks.captioning.BLIPCaptioner")
    @patch("src.workers.tasks.segmentation.SegFormerSegmenter")
    @patch("src.workers.tasks.detection.YOLODetector")
    def test_process_image_partial_failure(
        self,
        MockDetector,
        MockSegmenter,
        MockCaptioner,
        MockTracker,
        sample_segmentation_result,
    ):
        """Orchestration task records errors but continues pipeline."""
        # Detection fails
        det_instance = MagicMock()
        det_instance.detect.side_effect = RuntimeError("GPU OOM")
        MockDetector.return_value = det_instance

        # Segmentation succeeds
        seg_instance = MagicMock()
        seg_instance.segment.return_value = sample_segmentation_result
        MockSegmenter.return_value = seg_instance

        # Captioning succeeds
        cap_instance = MagicMock()
        cap_instance.generate_caption.return_value = "A street scene."
        MockCaptioner.return_value = cap_instance

        # Tracker mock
        tracker_instance = MagicMock()
        MockTracker.return_value = tracker_instance

        from src.workers.tasks.image_processing import process_image_task

        result = process_image_task.apply(
            args=["img-002", "/tmp/test.jpg"]
        ).get()

        assert result["status"] == "failed"
        assert len(result["errors"]) >= 1
        assert result["errors"][0]["step"] == "detection"
        # Segmentation and captioning should still have run
        assert result["segmentation"] is not None
        assert result["caption"] is not None


# ---------------------------------------------------------------------------
# Task retry tests
# ---------------------------------------------------------------------------

class TestTaskRetry:
    @patch("src.workers.tasks.detection.YOLODetector")
    def test_detection_retry_config(self, MockDetector):
        """Detection task has correct retry configuration."""
        from src.workers.tasks.detection import run_yolo_detection

        assert run_yolo_detection.max_retries == 3
        assert run_yolo_detection.soft_time_limit == 120

    @patch("src.workers.tasks.segmentation.SegFormerSegmenter")
    def test_segmentation_retry_config(self, MockSegmenter):
        """Segmentation task has correct retry configuration."""
        from src.workers.tasks.segmentation import run_segmentation

        assert run_segmentation.max_retries == 3
        assert run_segmentation.soft_time_limit == 120

    @patch("src.workers.tasks.captioning.BLIPCaptioner")
    def test_captioning_retry_config(self, MockCaptioner):
        """Captioning task has correct retry configuration."""
        from src.workers.tasks.captioning import run_captioning

        assert run_captioning.max_retries == 3
        assert run_captioning.soft_time_limit == 120


# ---------------------------------------------------------------------------
# Progress tracker tests
# ---------------------------------------------------------------------------

class TestProgressTracker:
    def test_update_progress(self, mock_redis):
        """update_progress stores data in Redis."""
        from src.workers.progress_tracker import ProgressTracker

        tracker = ProgressTracker(redis_client=mock_redis)
        tracker.update_progress(
            task_id="task-123",
            progress=50,
            message="Processing",
            step="detection",
        )

        mock_redis.setex.assert_called_once()
        key = mock_redis.setex.call_args[0][0]
        assert key == "task_progress:task-123"

        stored = json.loads(mock_redis.setex.call_args[0][2])
        assert stored["progress"] == 50
        assert stored["message"] == "Processing"
        assert stored["step"] == "detection"

    def test_get_progress_exists(self, mock_redis):
        """get_progress returns stored data when entry exists."""
        from src.workers.progress_tracker import ProgressTracker

        tracker = ProgressTracker(redis_client=mock_redis)

        # Store data first
        data = json.dumps({
            "task_id": "task-456",
            "progress": 75,
            "message": "Running segmentation",
            "step": "segmentation",
            "updated_at": 1234567890.0,
        })
        mock_redis._store["task_progress:task-456"] = data

        result = tracker.get_progress("task-456")

        assert result["progress"] == 75
        assert result["step"] == "segmentation"

    def test_get_progress_not_found(self, mock_redis):
        """get_progress returns default pending dict when no entry exists."""
        from src.workers.progress_tracker import ProgressTracker

        tracker = ProgressTracker(redis_client=mock_redis)
        result = tracker.get_progress("nonexistent-task")

        assert result["progress"] == 0
        assert result["step"] == "pending"
        assert result["message"] == "Pending"

    def test_update_then_get(self, mock_redis):
        """Round-trip: update then get returns same values."""
        from src.workers.progress_tracker import ProgressTracker

        tracker = ProgressTracker(redis_client=mock_redis)
        tracker.update_progress(
            task_id="task-789",
            progress=100,
            message="Done",
            step="completed",
        )

        result = tracker.get_progress("task-789")
        assert result["progress"] == 100
        assert result["message"] == "Done"
        assert result["step"] == "completed"


# ---------------------------------------------------------------------------
# Batch processing tests
# ---------------------------------------------------------------------------

class TestBatchProcessingTask:
    @patch("src.workers.tasks.image_processing.ProgressTracker")
    @patch("src.workers.tasks.captioning.BLIPCaptioner")
    @patch("src.workers.tasks.segmentation.SegFormerSegmenter")
    @patch("src.workers.tasks.detection.YOLODetector")
    def test_process_batch_success(
        self,
        MockDetector,
        MockSegmenter,
        MockCaptioner,
        MockTracker,
        sample_detection,
        sample_segmentation_result,
    ):
        """Batch task processes multiple images and returns summary."""
        # Setup mocks
        det_instance = MagicMock()
        det_instance.detect.return_value = [sample_detection]
        MockDetector.return_value = det_instance

        seg_instance = MagicMock()
        seg_instance.segment.return_value = sample_segmentation_result
        MockSegmenter.return_value = seg_instance

        cap_instance = MagicMock()
        cap_instance.generate_caption.return_value = "A street."
        MockCaptioner.return_value = cap_instance

        tracker_instance = MagicMock()
        MockTracker.return_value = tracker_instance

        from src.workers.tasks.batch_processing import process_batch_task

        image_ids = ["img-001", "img-002"]
        image_paths = ["/tmp/img1.jpg", "/tmp/img2.jpg"]

        result = process_batch_task.apply(
            args=[image_ids, image_paths]
        ).get()

        assert result["total"] == 2
        assert result["completed"] == 2
        assert result["failed"] == 0
        assert len(result["results"]) == 2
        assert result["processing_time_ms"] > 0

    @patch("src.workers.tasks.image_processing.ProgressTracker")
    @patch("src.workers.tasks.captioning.BLIPCaptioner")
    @patch("src.workers.tasks.segmentation.SegFormerSegmenter")
    @patch("src.workers.tasks.detection.YOLODetector")
    def test_process_batch_mismatched_lengths(
        self,
        MockDetector,
        MockSegmenter,
        MockCaptioner,
        MockTracker,
    ):
        """Batch task raises ValueError when ids and paths differ in length."""
        from src.workers.tasks.batch_processing import process_batch_task

        with pytest.raises(ValueError, match="same length"):
            process_batch_task.apply(
                args=[["img-001"], ["/tmp/a.jpg", "/tmp/b.jpg"]]
            ).get()
