"""Unit tests for the SegFormer segmentation pipeline."""

from __future__ import annotations

from dataclasses import fields
from pathlib import Path
from typing import List
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.ai.segmentation.metrics import SegmentationMetrics
from src.ai.segmentation.postprocessor import SegmentationPostprocessor
from src.ai.segmentation.segformer import SegFormerSegmenter
from src.ai.segmentation.segmentation_result import SegmentationResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_segmentation_result(
    mask: list | None = None,
    class_labels: List[str] | None = None,
    class_counts: dict | None = None,
    sidewalk_coverage: float = 0.25,
    inference_time_ms: float = 42.0,
) -> SegmentationResult:
    return SegmentationResult(
        mask=mask or [[0, 1], [1, 0]],
        class_labels=class_labels or ["wall", "building"],
        class_counts=class_counts or {"wall": 2, "building": 2},
        sidewalk_coverage=sidewalk_coverage,
        inference_time_ms=inference_time_ms,
    )


def _build_mock_segformer_output(num_classes: int = 150, h: int = 128, w: int = 128):
    """Create a mock that mimics SegFormer model output with logits tensor."""
    import torch

    mock_output = MagicMock()
    # logits shape: (batch=1, num_classes, h, w)
    logits = torch.randn(1, num_classes, h, w)
    mock_output.logits = logits
    return mock_output


def _create_test_image(tmp_path: Path, name: str = "test.jpg") -> Path:
    """Write a minimal valid JPEG file and return its path."""
    from PIL import Image

    img = Image.new("RGB", (64, 64), color=(128, 128, 128))
    path = tmp_path / name
    img.save(str(path), format="JPEG")
    return path


# ---------------------------------------------------------------------------
# SegmentationResult dataclass tests
# ---------------------------------------------------------------------------

class TestSegmentationResult:
    def test_dataclass_fields(self):
        """SegmentationResult has exactly the expected fields."""
        field_names = {f.name for f in fields(SegmentationResult)}
        assert field_names == {
            "mask",
            "class_labels",
            "class_counts",
            "sidewalk_coverage",
            "inference_time_ms",
        }

    def test_creation(self):
        result = _make_segmentation_result()
        assert result.mask == [[0, 1], [1, 0]]
        assert result.class_labels == ["wall", "building"]
        assert result.class_counts == {"wall": 2, "building": 2}
        assert result.sidewalk_coverage == 0.25
        assert result.inference_time_ms == 42.0

    def test_default_values(self):
        result = SegmentationResult(
            mask=[[0]],
            class_labels=["background"],
        )
        assert result.class_counts == {}
        assert result.sidewalk_coverage == 0.0
        assert result.inference_time_ms == 0.0

    def test_mask_is_serializable(self):
        """Mask should be a plain list (JSON-serializable)."""
        import json

        result = _make_segmentation_result()
        serialized = json.dumps(result.mask)
        assert isinstance(serialized, str)


# ---------------------------------------------------------------------------
# SegFormerSegmenter init tests
# ---------------------------------------------------------------------------

class TestSegFormerSegmenterInit:
    def test_default_model_name(self):
        segmenter = SegFormerSegmenter()
        assert segmenter.model_name == "nvidia/segformer-b3-finetuned-ade-512-512"

    def test_custom_model_name(self):
        segmenter = SegFormerSegmenter(model_name="nvidia/segformer-b0-finetuned-ade-512-512")
        assert segmenter.model_name == "nvidia/segformer-b0-finetuned-ade-512-512"

    def test_device_defaults_to_cpu_when_no_cuda(self):
        with patch("src.ai.segmentation.segformer.SegFormerSegmenter._detect_device", return_value="cpu"):
            segmenter = SegFormerSegmenter()
            assert segmenter.device == "cpu"

    def test_explicit_device(self):
        segmenter = SegFormerSegmenter(device="cpu")
        assert segmenter.device == "cpu"


# ---------------------------------------------------------------------------
# SegFormerSegmenter.segment tests
# ---------------------------------------------------------------------------

class TestSegFormerSegmenterSegment:
    @patch("src.ai.segmentation.segformer.SegFormerSegmenter._load_model")
    def test_single_image_returns_segmentation_result(self, mock_load, tmp_path):
        """segment() returns a SegmentationResult with the expected fields."""
        import torch

        img_path = _create_test_image(tmp_path)

        # Set up mock model
        mock_model = MagicMock()
        mock_output = _build_mock_segformer_output(num_classes=150, h=16, w=16)
        mock_model.return_value = mock_output
        mock_model.config = MagicMock()
        mock_model.config.id2label = {i: f"class_{i}" for i in range(150)}
        mock_model.eval = MagicMock()

        # Set up mock processor
        mock_processor = MagicMock()
        mock_processor.return_value = {"pixel_values": torch.randn(1, 3, 512, 512)}

        segmenter = SegFormerSegmenter(device="cpu")
        segmenter._model = mock_model
        segmenter._processor = mock_processor
        segmenter._class_labels = [f"class_{i}" for i in range(150)]

        result = segmenter.segment(img_path)

        assert isinstance(result, SegmentationResult)
        assert isinstance(result.mask, list)
        assert len(result.mask) == 64  # original image height
        assert len(result.mask[0]) == 64  # original image width
        assert isinstance(result.class_labels, list)
        assert isinstance(result.class_counts, dict)
        assert result.inference_time_ms > 0

    def test_missing_image_raises(self):
        segmenter = SegFormerSegmenter()
        with pytest.raises(FileNotFoundError):
            segmenter.segment(Path("/nonexistent/image.jpg"))

    @patch("src.ai.segmentation.segformer.SegFormerSegmenter._load_model")
    def test_sidewalk_coverage_calculated(self, mock_load, tmp_path):
        """sidewalk_coverage is populated based on class_id 11."""
        import torch

        img_path = _create_test_image(tmp_path)

        # Create logits where class 11 dominates half the image
        logits = torch.full((1, 150, 16, 16), -10.0)
        logits[0, 0, :, :] = 0.0  # background default
        logits[0, 11, :8, :] = 10.0  # sidewalk in top half

        mock_output = MagicMock()
        mock_output.logits = logits

        mock_model = MagicMock()
        mock_model.return_value = mock_output
        mock_model.config = MagicMock()
        mock_model.config.id2label = {i: f"class_{i}" for i in range(150)}
        mock_model.eval = MagicMock()

        mock_processor = MagicMock()
        mock_processor.return_value = {"pixel_values": torch.randn(1, 3, 512, 512)}

        segmenter = SegFormerSegmenter(device="cpu")
        segmenter._model = mock_model
        segmenter._processor = mock_processor
        segmenter._class_labels = [f"class_{i}" for i in range(150)]

        result = segmenter.segment(img_path)

        # Sidewalk should cover approximately half the image
        assert result.sidewalk_coverage > 0.0
        assert result.sidewalk_coverage <= 1.0


# ---------------------------------------------------------------------------
# Batch segmentation tests
# ---------------------------------------------------------------------------

class TestSegFormerSegmenterBatch:
    @patch("src.ai.segmentation.segformer.SegFormerSegmenter._load_model")
    def test_batch_segmentation(self, mock_load, tmp_path):
        """segment_batch returns one SegmentationResult per image."""
        import torch

        images = [_create_test_image(tmp_path, f"img_{i}.jpg") for i in range(3)]

        mock_output = _build_mock_segformer_output(num_classes=150, h=16, w=16)
        mock_model = MagicMock()
        mock_model.return_value = mock_output
        mock_model.config = MagicMock()
        mock_model.config.id2label = {i: f"class_{i}" for i in range(150)}
        mock_model.eval = MagicMock()

        mock_processor = MagicMock()
        mock_processor.return_value = {"pixel_values": torch.randn(1, 3, 512, 512)}

        segmenter = SegFormerSegmenter(device="cpu")
        segmenter._model = mock_model
        segmenter._processor = mock_processor
        segmenter._class_labels = [f"class_{i}" for i in range(150)]

        results = segmenter.segment_batch(images)

        assert len(results) == 3
        for r in results:
            assert isinstance(r, SegmentationResult)


# ---------------------------------------------------------------------------
# Metrics tests
# ---------------------------------------------------------------------------

class TestSegmentationMetricsIoU:
    def test_perfect_overlap(self):
        """IoU of identical masks for a given class should be 1.0."""
        mask = np.array([[1, 1, 0], [0, 1, 1]], dtype=np.int32)
        iou = SegmentationMetrics.calculate_iou(mask, mask, class_id=1)
        assert iou == pytest.approx(1.0)

    def test_no_overlap(self):
        """IoU should be 0.0 when pred and gt have no shared pixels."""
        pred = np.array([[1, 1, 1], [0, 0, 0]], dtype=np.int32)
        gt = np.array([[0, 0, 0], [1, 1, 1]], dtype=np.int32)
        iou = SegmentationMetrics.calculate_iou(pred, gt, class_id=1)
        assert iou == pytest.approx(0.0)

    def test_partial_overlap(self):
        """IoU for partial overlap should be between 0 and 1."""
        pred = np.array([[1, 1, 0], [0, 0, 0]], dtype=np.int32)
        gt = np.array([[0, 1, 1], [0, 0, 0]], dtype=np.int32)
        # Intersection = 1 pixel, Union = 3 pixels
        iou = SegmentationMetrics.calculate_iou(pred, gt, class_id=1)
        assert iou == pytest.approx(1.0 / 3.0)

    def test_class_absent_from_both(self):
        """IoU is 0.0 when the class is absent from both masks."""
        mask = np.zeros((4, 4), dtype=np.int32)
        iou = SegmentationMetrics.calculate_iou(mask, mask, class_id=5)
        assert iou == pytest.approx(0.0)


class TestSegmentationMetricsMeanIoU:
    def test_identical_masks(self):
        """Mean IoU of identical masks should be 1.0."""
        mask = np.array([[0, 1, 2], [2, 1, 0]], dtype=np.int32)
        miou = SegmentationMetrics.calculate_mean_iou(mask, mask)
        assert miou == pytest.approx(1.0)

    def test_completely_different_masks(self):
        """Mean IoU of completely non-overlapping classes should be 0.0."""
        pred = np.full((4, 4), 0, dtype=np.int32)
        gt = np.full((4, 4), 1, dtype=np.int32)
        miou = SegmentationMetrics.calculate_mean_iou(pred, gt)
        assert miou == pytest.approx(0.0)

    def test_mean_iou_across_classes(self):
        """Mean IoU averages over all present classes."""
        pred = np.array([[0, 0, 1, 1]], dtype=np.int32)
        gt = np.array([[0, 0, 1, 1]], dtype=np.int32)
        miou = SegmentationMetrics.calculate_mean_iou(pred, gt)
        assert miou == pytest.approx(1.0)


class TestSegmentationMetricsCoverage:
    def test_full_coverage(self):
        mask = np.full((10, 10), 5, dtype=np.int32)
        assert SegmentationMetrics.calculate_coverage(mask, 5) == pytest.approx(1.0)

    def test_no_coverage(self):
        mask = np.zeros((10, 10), dtype=np.int32)
        assert SegmentationMetrics.calculate_coverage(mask, 5) == pytest.approx(0.0)

    def test_partial_coverage(self):
        mask = np.zeros((10, 10), dtype=np.int32)
        mask[:5, :] = 3  # 50 out of 100 pixels
        assert SegmentationMetrics.calculate_coverage(mask, 3) == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Postprocessor tests
# ---------------------------------------------------------------------------

class TestMaskSmoothing:
    def test_smooth_preserves_shape(self):
        mask = np.random.randint(0, 5, size=(64, 64), dtype=np.int32)
        pp = SegmentationPostprocessor()
        smoothed = pp.smooth_mask(mask, kernel_size=3)
        assert smoothed.shape == mask.shape

    def test_smooth_removes_noise(self):
        """A single noisy pixel in a uniform region should be smoothed out."""
        mask = np.zeros((11, 11), dtype=np.int32)
        mask[5, 5] = 1  # single noisy pixel
        pp = SegmentationPostprocessor()
        smoothed = pp.smooth_mask(mask, kernel_size=3)
        assert smoothed[5, 5] == 0

    def test_smooth_preserves_dtype(self):
        mask = np.ones((8, 8), dtype=np.int32) * 2
        pp = SegmentationPostprocessor()
        smoothed = pp.smooth_mask(mask)
        assert smoothed.dtype == mask.dtype


class TestHoleFilling:
    def test_fills_small_interior_hole(self):
        """A small hole surrounded by a class should be filled."""
        mask = np.ones((20, 20), dtype=np.int32)
        # Create a small 3x3 hole of class 0 in the interior
        mask[9:12, 9:12] = 0  # 9 pixels < min_hole_size=100

        pp = SegmentationPostprocessor()
        filled = pp.fill_holes(mask, min_hole_size=100)

        # The hole should be filled with class 1
        assert np.all(filled[9:12, 9:12] == 1)

    def test_preserves_large_regions(self):
        """Regions larger than min_hole_size are not filled."""
        mask = np.ones((20, 20), dtype=np.int32)
        # Create a large hole
        mask[2:18, 2:18] = 0  # 256 pixels > min_hole_size=100

        pp = SegmentationPostprocessor()
        filled = pp.fill_holes(mask, min_hole_size=100)

        # Large region should remain unfilled
        assert np.any(filled[2:18, 2:18] == 0)

    def test_preserves_shape(self):
        mask = np.zeros((30, 30), dtype=np.int32)
        pp = SegmentationPostprocessor()
        filled = pp.fill_holes(mask)
        assert filled.shape == mask.shape


class TestExtractSidewalkCoverage:
    def test_full_sidewalk(self):
        mask = np.full((10, 10), 11, dtype=np.int32)
        pp = SegmentationPostprocessor()
        assert pp.extract_sidewalk_coverage(mask) == pytest.approx(1.0)

    def test_no_sidewalk(self):
        mask = np.zeros((10, 10), dtype=np.int32)
        pp = SegmentationPostprocessor()
        assert pp.extract_sidewalk_coverage(mask) == pytest.approx(0.0)

    def test_partial_sidewalk(self):
        mask = np.zeros((10, 10), dtype=np.int32)
        mask[:, :5] = 11  # 50% sidewalk
        pp = SegmentationPostprocessor()
        coverage = pp.extract_sidewalk_coverage(mask)
        assert coverage == pytest.approx(0.5)

    def test_custom_class_id(self):
        mask = np.full((10, 10), 42, dtype=np.int32)
        pp = SegmentationPostprocessor()
        assert pp.extract_sidewalk_coverage(mask, sidewalk_class_id=42) == pytest.approx(1.0)

    def test_empty_mask(self):
        mask = np.array([], dtype=np.int32)
        pp = SegmentationPostprocessor()
        assert pp.extract_sidewalk_coverage(mask) == pytest.approx(0.0)
