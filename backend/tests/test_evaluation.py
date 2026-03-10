"""Tests for the KALYE model evaluation framework."""

from __future__ import annotations

import json
from unittest.mock import mock_open, patch

import numpy as np
import pytest

from backend.src.evaluation.dataset_loader import EvaluationDatasetLoader
from backend.src.evaluation.evaluator import ModelEvaluator, THRESHOLDS
from backend.src.evaluation.metrics import BiasMetrics, DetectionMetrics, SegmentationMetrics


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def detection_metrics():
    return DetectionMetrics()


@pytest.fixture
def segmentation_metrics():
    return SegmentationMetrics()


@pytest.fixture
def bias_metrics():
    return BiasMetrics()


@pytest.fixture
def evaluator():
    loader = EvaluationDatasetLoader(data_dir="data/evals")
    return ModelEvaluator(
        dataset_loader=loader,
        detection_metrics=DetectionMetrics(),
        segmentation_metrics=SegmentationMetrics(),
        bias_metrics=BiasMetrics(),
    )


# ---------------------------------------------------------------------------
# Detection Metrics Tests
# ---------------------------------------------------------------------------

class TestDetectionMetrics:
    def test_iou_box_perfect_overlap(self, detection_metrics):
        box = [0, 0, 10, 10]
        assert detection_metrics._calculate_iou_box(box, box) == pytest.approx(1.0)

    def test_iou_box_no_overlap(self, detection_metrics):
        box1 = [0, 0, 10, 10]
        box2 = [20, 20, 30, 30]
        assert detection_metrics._calculate_iou_box(box1, box2) == pytest.approx(0.0)

    def test_iou_box_partial_overlap(self, detection_metrics):
        box1 = [0, 0, 10, 10]
        box2 = [5, 5, 15, 15]
        # Intersection: 5x5=25, Union: 100+100-25=175
        assert detection_metrics._calculate_iou_box(box1, box2) == pytest.approx(
            25.0 / 175.0
        )

    def test_map_perfect_predictions(self, detection_metrics):
        gt = [
            {"bbox": [0, 0, 10, 10], "class_id": 0},
            {"bbox": [20, 20, 30, 30], "class_id": 0},
        ]
        preds = [
            {"bbox": [0, 0, 10, 10], "class_id": 0, "score": 0.9},
            {"bbox": [20, 20, 30, 30], "class_id": 0, "score": 0.8},
        ]
        map_score = detection_metrics.calculate_map(preds, gt)
        assert map_score == pytest.approx(1.0)

    def test_map_no_predictions(self, detection_metrics):
        gt = [{"bbox": [0, 0, 10, 10], "class_id": 0}]
        assert detection_metrics.calculate_map([], gt) == pytest.approx(0.0)

    def test_map_no_ground_truth(self, detection_metrics):
        preds = [{"bbox": [0, 0, 10, 10], "class_id": 0, "score": 0.9}]
        # No GT but predictions exist -> 0 for classes with preds only
        assert detection_metrics.calculate_map(preds, []) == pytest.approx(0.0)

    def test_map_empty_both(self, detection_metrics):
        assert detection_metrics.calculate_map([], []) == pytest.approx(1.0)

    def test_precision_recall_perfect(self, detection_metrics):
        gt = [{"bbox": [0, 0, 10, 10], "class_id": 0}]
        preds = [{"bbox": [0, 0, 10, 10], "class_id": 0, "score": 0.9}]
        precision, recall = detection_metrics.calculate_precision_recall(preds, gt)
        assert precision == pytest.approx(1.0)
        assert recall == pytest.approx(1.0)

    def test_precision_recall_false_positive(self, detection_metrics):
        gt = [{"bbox": [0, 0, 10, 10], "class_id": 0}]
        preds = [
            {"bbox": [0, 0, 10, 10], "class_id": 0, "score": 0.9},
            {"bbox": [50, 50, 60, 60], "class_id": 0, "score": 0.5},
        ]
        precision, recall = detection_metrics.calculate_precision_recall(preds, gt)
        assert precision == pytest.approx(0.5)  # 1 TP / 2 preds
        assert recall == pytest.approx(1.0)  # 1 TP / 1 GT

    def test_precision_recall_false_negative(self, detection_metrics):
        gt = [
            {"bbox": [0, 0, 10, 10], "class_id": 0},
            {"bbox": [20, 20, 30, 30], "class_id": 0},
        ]
        preds = [{"bbox": [0, 0, 10, 10], "class_id": 0, "score": 0.9}]
        precision, recall = detection_metrics.calculate_precision_recall(preds, gt)
        assert precision == pytest.approx(1.0)  # 1 TP / 1 pred
        assert recall == pytest.approx(0.5)  # 1 TP / 2 GT

    def test_f1_score(self, detection_metrics):
        assert detection_metrics.calculate_f1_score(1.0, 1.0) == pytest.approx(1.0)
        assert detection_metrics.calculate_f1_score(0.5, 0.5) == pytest.approx(0.5)
        assert detection_metrics.calculate_f1_score(0.0, 0.0) == pytest.approx(0.0)
        # precision=0.8, recall=0.6 -> F1 = 2*0.8*0.6/(0.8+0.6)
        expected = 2 * 0.8 * 0.6 / (0.8 + 0.6)
        assert detection_metrics.calculate_f1_score(0.8, 0.6) == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Segmentation Metrics Tests
# ---------------------------------------------------------------------------

class TestSegmentationMetrics:
    def test_iou_perfect_mask(self, segmentation_metrics):
        mask = np.array([[0, 1], [1, 0]])
        assert segmentation_metrics.calculate_iou(mask, mask, class_id=1) == pytest.approx(1.0)

    def test_iou_no_overlap(self, segmentation_metrics):
        pred = np.array([[1, 1], [1, 1]])
        gt = np.array([[0, 0], [0, 0]])
        assert segmentation_metrics.calculate_iou(pred, gt, class_id=1) == pytest.approx(0.0)

    def test_iou_partial_overlap(self, segmentation_metrics):
        pred = np.array([[1, 1, 0], [0, 0, 0]])
        gt = np.array([[1, 0, 0], [0, 0, 0]])
        # class_id=1: intersection=1, union=2
        assert segmentation_metrics.calculate_iou(pred, gt, class_id=1) == pytest.approx(0.5)

    def test_iou_class_absent_both(self, segmentation_metrics):
        mask = np.zeros((3, 3), dtype=int)
        # class_id=5 not present in either -> union=0 -> return 1.0
        assert segmentation_metrics.calculate_iou(mask, mask, class_id=5) == pytest.approx(1.0)

    def test_mean_iou(self, segmentation_metrics):
        pred = np.array([[0, 1], [1, 0]])
        gt = np.array([[0, 1], [1, 0]])
        assert segmentation_metrics.calculate_mean_iou(pred, gt) == pytest.approx(1.0)

    def test_mean_iou_partial(self, segmentation_metrics):
        pred = np.array([[0, 0], [1, 1]])
        gt = np.array([[0, 1], [1, 0]])
        # class 0: pred has (0,0),(0,1); gt has (0,0),(1,1) -> inter=1, union=3 -> 1/3
        # class 1: pred has (1,0),(1,1); gt has (0,1),(1,0) -> inter=1, union=3 -> 1/3
        miou = segmentation_metrics.calculate_mean_iou(pred, gt)
        expected = (1 / 3 + 1 / 3) / 2
        assert miou == pytest.approx(expected)

    def test_pixel_accuracy_perfect(self, segmentation_metrics):
        mask = np.array([[0, 1], [2, 3]])
        assert segmentation_metrics.calculate_pixel_accuracy(mask, mask) == pytest.approx(1.0)

    def test_pixel_accuracy_partial(self, segmentation_metrics):
        pred = np.array([[0, 1], [1, 0]])
        gt = np.array([[0, 0], [1, 1]])
        # Correct: (0,0) and (1,0) -> 2/4 = 0.5
        assert segmentation_metrics.calculate_pixel_accuracy(pred, gt) == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Bias Metrics Tests
# ---------------------------------------------------------------------------

class TestBiasMetrics:
    def test_district_variance_uniform(self, bias_metrics):
        results = {"A": 0.8, "B": 0.8, "C": 0.8}
        assert bias_metrics.calculate_district_variance(results) == pytest.approx(0.0)

    def test_district_variance_spread(self, bias_metrics):
        results = {"A": 0.9, "B": 0.7}
        expected_std = float(np.std([0.9, 0.7]))
        assert bias_metrics.calculate_district_variance(results) == pytest.approx(expected_std)

    def test_district_variance_empty(self, bias_metrics):
        assert bias_metrics.calculate_district_variance({}) == pytest.approx(0.0)

    def test_fairness_is_fair(self, bias_metrics):
        results = [
            {"district": "A", "score": 0.80},
            {"district": "B", "score": 0.82},
            {"district": "C", "score": 0.81},
        ]
        fairness = bias_metrics.test_fairness(results)
        assert fairness["is_fair"] is True
        assert fairness["variance"] < 0.10

    def test_fairness_is_unfair(self, bias_metrics):
        results = [
            {"district": "A", "score": 0.95},
            {"district": "B", "score": 0.50},
            {"district": "C", "score": 0.30},
        ]
        fairness = bias_metrics.test_fairness(results)
        assert fairness["is_fair"] is False
        assert fairness["variance"] >= 0.10

    def test_fairness_empty(self, bias_metrics):
        fairness = bias_metrics.test_fairness([])
        assert fairness["is_fair"] is True
        assert fairness["variance"] == 0.0


# ---------------------------------------------------------------------------
# Evaluator Tests
# ---------------------------------------------------------------------------

class TestModelEvaluator:
    def test_evaluate_detection_model(self, evaluator):
        gt = [
            {"bbox": [0, 0, 10, 10], "class_id": 0},
            {"bbox": [20, 20, 30, 30], "class_id": 0},
        ]
        preds = [
            {"bbox": [0, 0, 10, 10], "class_id": 0, "score": 0.9},
            {"bbox": [20, 20, 30, 30], "class_id": 0, "score": 0.8},
        ]
        results = evaluator.evaluate_detection_model(preds, gt)
        assert "mAP" in results
        assert "precision" in results
        assert "recall" in results
        assert "f1" in results
        assert results["mAP"] == pytest.approx(1.0)
        assert results["precision"] == pytest.approx(1.0)

    def test_evaluate_segmentation_model(self, evaluator):
        pred = np.array([[0, 1], [1, 0]])
        gt = np.array([[0, 1], [1, 0]])
        results = evaluator.evaluate_segmentation_model([pred], [gt])
        assert results["mean_iou"] == pytest.approx(1.0)
        assert results["pixel_accuracy"] == pytest.approx(1.0)

    def test_evaluate_segmentation_model_empty(self, evaluator):
        results = evaluator.evaluate_segmentation_model([], [])
        assert results["mean_iou"] == 0.0
        assert results["pixel_accuracy"] == 0.0

    def test_evaluate_bias(self, evaluator):
        districts = {"A": 0.80, "B": 0.82, "C": 0.81}
        results = evaluator.evaluate_bias(districts)
        assert "variance" in results
        assert "max_deviation" in results
        assert "is_fair" in results
        assert results["is_fair"] is True

    def test_generate_report(self, evaluator):
        detection = {"mAP": 0.85, "precision": 0.90, "recall": 0.80, "f1": 0.85}
        segmentation = {"mean_iou": 0.70, "pixel_accuracy": 0.85}
        bias = {"variance": 0.05, "max_deviation": 0.03, "is_fair": True}

        report = evaluator.generate_report(detection, segmentation, bias)

        assert "timestamp" in report
        assert "thresholds" in report
        assert "results" in report
        assert "threshold_checks" in report
        assert report["results"]["detection"] == detection
        assert report["results"]["segmentation"] == segmentation
        assert report["results"]["bias"] == bias

    def test_check_thresholds_pass(self, evaluator):
        report = {
            "results": {
                "detection": {"mAP": 0.85, "precision": 0.90},
                "segmentation": {"mean_iou": 0.70},
                "bias": {"variance": 0.05},
            }
        }
        checks = evaluator.check_thresholds(report)
        assert checks["overall_pass"] is True
        assert checks["detection_map"]["passed"] is True
        assert checks["detection_precision"]["passed"] is True
        assert checks["segmentation_iou"]["passed"] is True
        assert checks["bias_variance"]["passed"] is True

    def test_check_thresholds_fail_map(self, evaluator):
        report = {
            "results": {
                "detection": {"mAP": 0.50, "precision": 0.90},
                "segmentation": {"mean_iou": 0.70},
                "bias": {"variance": 0.05},
            }
        }
        checks = evaluator.check_thresholds(report)
        assert checks["overall_pass"] is False
        assert checks["detection_map"]["passed"] is False

    def test_check_thresholds_fail_precision(self, evaluator):
        report = {
            "results": {
                "detection": {"mAP": 0.80, "precision": 0.60},
                "segmentation": {"mean_iou": 0.70},
                "bias": {"variance": 0.05},
            }
        }
        checks = evaluator.check_thresholds(report)
        assert checks["overall_pass"] is False
        assert checks["detection_precision"]["passed"] is False

    def test_check_thresholds_fail_iou(self, evaluator):
        report = {
            "results": {
                "detection": {"mAP": 0.80, "precision": 0.90},
                "segmentation": {"mean_iou": 0.40},
                "bias": {"variance": 0.05},
            }
        }
        checks = evaluator.check_thresholds(report)
        assert checks["overall_pass"] is False
        assert checks["segmentation_iou"]["passed"] is False

    def test_check_thresholds_fail_bias(self, evaluator):
        report = {
            "results": {
                "detection": {"mAP": 0.80, "precision": 0.90},
                "segmentation": {"mean_iou": 0.70},
                "bias": {"variance": 0.20},
            }
        }
        checks = evaluator.check_thresholds(report)
        assert checks["overall_pass"] is False
        assert checks["bias_variance"]["passed"] is False


# ---------------------------------------------------------------------------
# Dataset Loader Tests
# ---------------------------------------------------------------------------

class TestDatasetLoader:
    def test_load_coco_annotations_valid(self, tmp_path):
        coco_data = {
            "images": [{"id": 1, "file_name": "img1.jpg"}],
            "annotations": [
                {"image_id": 1, "bbox": [10, 20, 30, 40], "category_id": 1}
            ],
            "categories": [{"id": 1, "name": "pothole"}],
        }
        ann_file = tmp_path / "annotations.json"
        ann_file.write_text(json.dumps(coco_data))

        loader = EvaluationDatasetLoader(data_dir=str(tmp_path))
        result = loader._load_coco_annotations(str(ann_file))
        assert "images" in result
        assert "annotations" in result
        assert "categories" in result

    def test_load_coco_annotations_missing_file(self):
        loader = EvaluationDatasetLoader(data_dir="nonexistent")
        with pytest.raises(FileNotFoundError):
            loader._load_coco_annotations("nonexistent/annotations.json")

    def test_load_coco_annotations_invalid_format(self, tmp_path):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text(json.dumps({"foo": "bar"}))

        loader = EvaluationDatasetLoader(data_dir=str(tmp_path))
        with pytest.raises(ValueError, match="Invalid COCO format"):
            loader._load_coco_annotations(str(bad_file))

    def test_load_detection_dataset(self, tmp_path):
        det_dir = tmp_path / "detection"
        det_dir.mkdir()
        coco_data = {
            "images": [
                {"id": 1, "file_name": "img1.jpg"},
                {"id": 2, "file_name": "img2.jpg"},
            ],
            "annotations": [
                {"image_id": 1, "bbox": [10, 20, 30, 40], "category_id": 1},
                {"image_id": 1, "bbox": [50, 60, 10, 20], "category_id": 2},
                {"image_id": 2, "bbox": [5, 5, 15, 15], "category_id": 1},
            ],
            "categories": [
                {"id": 1, "name": "pothole"},
                {"id": 2, "name": "obstruction"},
            ],
        }
        (det_dir / "annotations.json").write_text(json.dumps(coco_data))

        loader = EvaluationDatasetLoader(data_dir=str(tmp_path))
        dataset = loader.load_detection_dataset()

        assert len(dataset) == 2
        img1 = next(d for d in dataset if d["image_id"] == 1)
        assert len(img1["annotations"]) == 2
        # Check COCO bbox [x,y,w,h] -> [x1,y1,x2,y2] conversion
        ann = img1["annotations"][0]
        assert ann["bbox"] == [10, 20, 40, 60]  # [10, 20, 10+30, 20+40]

    def test_load_segmentation_dataset(self, tmp_path):
        seg_dir = tmp_path / "segmentation"
        seg_dir.mkdir()
        seg_data = {
            "images": [
                {"id": 1, "file_name": "img1.jpg"},
                {"id": 2, "file_name": "img2.jpg", "mask_file": "mask2.png"},
            ]
        }
        (seg_dir / "annotations.json").write_text(json.dumps(seg_data))

        loader = EvaluationDatasetLoader(data_dir=str(tmp_path))
        dataset = loader.load_segmentation_dataset()

        assert len(dataset) == 2
        assert dataset[0]["image_id"] == 1
        assert "img1.jpg" in dataset[0]["image_path"]
        assert dataset[0]["mask_path"].endswith("img1.png")  # auto-derived
        assert dataset[1]["mask_path"].endswith("mask2.png")  # explicit

    def test_load_segmentation_missing(self):
        loader = EvaluationDatasetLoader(data_dir="nonexistent")
        with pytest.raises(FileNotFoundError):
            loader.load_segmentation_dataset()

    def test_load_walkability_ground_truth(self, tmp_path):
        walk_dir = tmp_path / "walkability"
        walk_dir.mkdir()
        gt_data = {
            "Makati": {"score": 0.75, "notes": "Good sidewalks"},
            "Tondo": {"score": 0.45, "notes": "Poor infrastructure"},
        }
        (walk_dir / "ground_truth.json").write_text(json.dumps(gt_data))

        loader = EvaluationDatasetLoader(data_dir=str(tmp_path))
        result = loader.load_walkability_ground_truth()

        assert "Makati" in result
        assert result["Makati"]["score"] == 0.75

    def test_load_walkability_missing(self):
        loader = EvaluationDatasetLoader(data_dir="nonexistent")
        with pytest.raises(FileNotFoundError):
            loader.load_walkability_ground_truth()
