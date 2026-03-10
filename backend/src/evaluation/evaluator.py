"""Model evaluator orchestrating metrics computation and report generation."""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

from backend.src.evaluation.dataset_loader import EvaluationDatasetLoader
from backend.src.evaluation.metrics import BiasMetrics, DetectionMetrics, SegmentationMetrics

# Thresholds from CLAUDE.md
THRESHOLDS = {
    "detection_map": 0.75,
    "segmentation_iou": 0.65,
    "detection_precision": 0.80,
    "bias_variance": 0.10,
}


class ModelEvaluator:
    """Orchestrates evaluation of KALYE AI models against defined thresholds."""

    def __init__(
        self,
        dataset_loader: EvaluationDatasetLoader,
        detection_metrics: DetectionMetrics,
        segmentation_metrics: SegmentationMetrics,
        bias_metrics: BiasMetrics,
    ) -> None:
        self.dataset_loader = dataset_loader
        self.detection_metrics = detection_metrics
        self.segmentation_metrics = segmentation_metrics
        self.bias_metrics = bias_metrics

    def evaluate_detection_model(
        self,
        predictions: list[dict],
        ground_truth: list[dict],
    ) -> dict:
        """Evaluate a detection model's predictions against ground truth.

        Args:
            predictions: List of prediction dicts with bbox, score, class_id.
            ground_truth: List of ground truth dicts with bbox, class_id.

        Returns:
            Dict with mAP, precision, recall, f1.
        """
        map_score = self.detection_metrics.calculate_map(predictions, ground_truth)
        precision, recall = self.detection_metrics.calculate_precision_recall(
            predictions, ground_truth
        )
        f1 = self.detection_metrics.calculate_f1_score(precision, recall)

        return {
            "mAP": float(map_score),
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1),
        }

    def evaluate_segmentation_model(
        self,
        predictions: list[np.ndarray],
        ground_truths: list[np.ndarray],
    ) -> dict:
        """Evaluate a segmentation model's predictions against ground truth masks.

        Args:
            predictions: List of predicted masks (H, W).
            ground_truths: List of ground truth masks (H, W).

        Returns:
            Dict with mean_iou and pixel_accuracy.
        """
        if not predictions or not ground_truths:
            return {"mean_iou": 0.0, "pixel_accuracy": 0.0}

        ious = []
        accuracies = []
        for pred, gt in zip(predictions, ground_truths):
            ious.append(self.segmentation_metrics.calculate_mean_iou(pred, gt))
            accuracies.append(self.segmentation_metrics.calculate_pixel_accuracy(pred, gt))

        return {
            "mean_iou": float(np.mean(ious)),
            "pixel_accuracy": float(np.mean(accuracies)),
        }

    def evaluate_bias(self, results_by_district: dict[str, float]) -> dict:
        """Evaluate model fairness across districts.

        Args:
            results_by_district: Dict mapping district name to performance score.

        Returns:
            Dict with variance, max_deviation, is_fair.
        """
        variance = self.bias_metrics.calculate_district_variance(results_by_district)
        results_list = [
            {"district": d, "score": s} for d, s in results_by_district.items()
        ]
        fairness = self.bias_metrics.test_fairness(results_list)
        return fairness

    def generate_report(
        self,
        detection_results: dict | None = None,
        segmentation_results: dict | None = None,
        bias_results: dict | None = None,
    ) -> dict:
        """Generate a comprehensive evaluation report.

        Args:
            detection_results: Output from evaluate_detection_model.
            segmentation_results: Output from evaluate_segmentation_model.
            bias_results: Output from evaluate_bias.

        Returns:
            Full report dict with results, thresholds, and pass/fail status.
        """
        report: dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "thresholds": THRESHOLDS,
            "results": {},
        }

        if detection_results is not None:
            report["results"]["detection"] = detection_results
        if segmentation_results is not None:
            report["results"]["segmentation"] = segmentation_results
        if bias_results is not None:
            report["results"]["bias"] = bias_results

        report["threshold_checks"] = self.check_thresholds(report)
        return report

    def check_thresholds(self, report: dict) -> dict:
        """Check evaluation results against defined thresholds.

        Args:
            report: Report dict with results section.

        Returns:
            Dict with per-metric pass/fail and an overall_pass flag.
        """
        results = report.get("results", {})
        checks: dict = {}

        detection = results.get("detection", {})
        if "mAP" in detection:
            checks["detection_map"] = {
                "value": detection["mAP"],
                "threshold": THRESHOLDS["detection_map"],
                "passed": detection["mAP"] >= THRESHOLDS["detection_map"],
            }
        if "precision" in detection:
            checks["detection_precision"] = {
                "value": detection["precision"],
                "threshold": THRESHOLDS["detection_precision"],
                "passed": detection["precision"] >= THRESHOLDS["detection_precision"],
            }

        segmentation = results.get("segmentation", {})
        if "mean_iou" in segmentation:
            checks["segmentation_iou"] = {
                "value": segmentation["mean_iou"],
                "threshold": THRESHOLDS["segmentation_iou"],
                "passed": segmentation["mean_iou"] >= THRESHOLDS["segmentation_iou"],
            }

        bias = results.get("bias", {})
        if "variance" in bias:
            checks["bias_variance"] = {
                "value": bias["variance"],
                "threshold": THRESHOLDS["bias_variance"],
                "passed": bias["variance"] < THRESHOLDS["bias_variance"],
            }

        checks["overall_pass"] = all(
            c["passed"] for c in checks.values() if isinstance(c, dict) and "passed" in c
        )

        return checks
