"""Evaluation metrics for KALYE AI models."""

from __future__ import annotations

import numpy as np


class DetectionMetrics:
    """Metrics for object detection models (e.g., YOLOv8 pothole/obstruction detection)."""

    def calculate_map(
        self,
        predictions: list[dict],
        ground_truth: list[dict],
        iou_threshold: float = 0.5,
    ) -> float:
        """Calculate mean Average Precision at a given IoU threshold.

        Args:
            predictions: List of dicts with keys: bbox [x1,y1,x2,y2], score, class_id.
            ground_truth: List of dicts with keys: bbox [x1,y1,x2,y2], class_id.
            iou_threshold: IoU threshold for a prediction to count as a true positive.

        Returns:
            mAP value in [0, 1].
        """
        if not ground_truth:
            return 1.0 if not predictions else 0.0
        if not predictions:
            return 0.0

        # Group by class
        gt_by_class: dict[int, list[dict]] = {}
        for gt in ground_truth:
            cid = gt["class_id"]
            gt_by_class.setdefault(cid, []).append(gt)

        pred_by_class: dict[int, list[dict]] = {}
        for pred in predictions:
            cid = pred["class_id"]
            pred_by_class.setdefault(cid, []).append(pred)

        all_classes = set(gt_by_class.keys()) | set(pred_by_class.keys())
        aps: list[float] = []

        for cid in all_classes:
            class_gt = gt_by_class.get(cid, [])
            class_preds = sorted(
                pred_by_class.get(cid, []), key=lambda p: p.get("score", 0), reverse=True
            )

            if not class_gt:
                # All predictions for this class are false positives -> AP = 0
                aps.append(0.0)
                continue
            if not class_preds:
                # No predictions but there are ground truths -> AP = 0
                aps.append(0.0)
                continue

            matched = [False] * len(class_gt)
            tp = []
            fp = []

            for pred in class_preds:
                best_iou = 0.0
                best_idx = -1
                for idx, gt in enumerate(class_gt):
                    iou = self._calculate_iou_box(pred["bbox"], gt["bbox"])
                    if iou > best_iou:
                        best_iou = iou
                        best_idx = idx

                if best_iou >= iou_threshold and not matched[best_idx]:
                    tp.append(1)
                    fp.append(0)
                    matched[best_idx] = True
                else:
                    tp.append(0)
                    fp.append(1)

            tp_cumsum = np.cumsum(tp).astype(float)
            fp_cumsum = np.cumsum(fp).astype(float)

            recalls = tp_cumsum / len(class_gt)
            precisions = tp_cumsum / (tp_cumsum + fp_cumsum)

            # Compute AP using 11-point interpolation
            ap = 0.0
            for t in np.linspace(0, 1, 11):
                prec_at_recall = precisions[recalls >= t]
                if len(prec_at_recall) > 0:
                    ap += np.max(prec_at_recall)
            ap /= 11.0
            aps.append(float(ap))

        return float(np.mean(aps)) if aps else 0.0

    def calculate_precision_recall(
        self,
        predictions: list[dict],
        ground_truth: list[dict],
        iou_threshold: float = 0.5,
    ) -> tuple[float, float]:
        """Calculate precision and recall for detection results.

        Args:
            predictions: List of dicts with keys: bbox [x1,y1,x2,y2], score, class_id.
            ground_truth: List of dicts with keys: bbox [x1,y1,x2,y2], class_id.
            iou_threshold: IoU threshold for matching.

        Returns:
            Tuple of (precision, recall).
        """
        if not predictions and not ground_truth:
            return 1.0, 1.0
        if not predictions:
            return 1.0, 0.0
        if not ground_truth:
            return 0.0, 1.0

        matched_gt = set()
        true_positives = 0

        sorted_preds = sorted(predictions, key=lambda p: p.get("score", 0), reverse=True)

        for pred in sorted_preds:
            best_iou = 0.0
            best_idx = -1
            for idx, gt in enumerate(ground_truth):
                if idx in matched_gt:
                    continue
                if pred["class_id"] != gt["class_id"]:
                    continue
                iou = self._calculate_iou_box(pred["bbox"], gt["bbox"])
                if iou > best_iou:
                    best_iou = iou
                    best_idx = idx

            if best_iou >= iou_threshold and best_idx >= 0:
                true_positives += 1
                matched_gt.add(best_idx)

        precision = true_positives / len(predictions) if predictions else 0.0
        recall = true_positives / len(ground_truth) if ground_truth else 0.0
        return precision, recall

    def calculate_f1_score(self, precision: float, recall: float) -> float:
        """Calculate F1 score from precision and recall.

        Returns:
            F1 score in [0, 1].
        """
        if precision + recall == 0:
            return 0.0
        return 2 * (precision * recall) / (precision + recall)

    def _calculate_iou_box(self, box1: list[float], box2: list[float]) -> float:
        """Calculate Intersection over Union between two bounding boxes.

        Args:
            box1: [x1, y1, x2, y2] format.
            box2: [x1, y1, x2, y2] format.

        Returns:
            IoU value in [0, 1].
        """
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])

        intersection = max(0, x2 - x1) * max(0, y2 - y1)
        if intersection == 0:
            return 0.0

        area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
        area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
        union = area1 + area2 - intersection

        if union == 0:
            return 0.0
        return intersection / union


class SegmentationMetrics:
    """Metrics for semantic segmentation models (e.g., SegFormer sidewalk segmentation)."""

    def calculate_iou(
        self, pred_mask: np.ndarray, gt_mask: np.ndarray, class_id: int
    ) -> float:
        """Calculate IoU for a specific class.

        Args:
            pred_mask: Predicted segmentation mask (H, W) with integer class labels.
            gt_mask: Ground truth segmentation mask (H, W) with integer class labels.
            class_id: The class to compute IoU for.

        Returns:
            IoU value in [0, 1].
        """
        pred_binary = (pred_mask == class_id)
        gt_binary = (gt_mask == class_id)

        intersection = np.logical_and(pred_binary, gt_binary).sum()
        union = np.logical_or(pred_binary, gt_binary).sum()

        if union == 0:
            return 1.0  # Both masks have no pixels for this class
        return float(intersection / union)

    def calculate_mean_iou(
        self, pred_mask: np.ndarray, gt_mask: np.ndarray
    ) -> float:
        """Calculate mean IoU across all classes present in the ground truth.

        Args:
            pred_mask: Predicted segmentation mask (H, W).
            gt_mask: Ground truth segmentation mask (H, W).

        Returns:
            Mean IoU value in [0, 1].
        """
        classes = np.unique(np.concatenate([np.unique(pred_mask), np.unique(gt_mask)]))
        if len(classes) == 0:
            return 1.0

        ious = [self.calculate_iou(pred_mask, gt_mask, int(c)) for c in classes]
        return float(np.mean(ious))

    def calculate_pixel_accuracy(
        self, pred_mask: np.ndarray, gt_mask: np.ndarray
    ) -> float:
        """Calculate overall pixel accuracy.

        Args:
            pred_mask: Predicted segmentation mask (H, W).
            gt_mask: Ground truth segmentation mask (H, W).

        Returns:
            Pixel accuracy in [0, 1].
        """
        if gt_mask.size == 0:
            return 1.0
        correct = (pred_mask == gt_mask).sum()
        return float(correct / gt_mask.size)


class BiasMetrics:
    """Metrics for evaluating model fairness across districts/barangays."""

    def calculate_district_variance(self, results_by_district: dict[str, float]) -> float:
        """Calculate variance of model performance across districts.

        Args:
            results_by_district: Dict mapping district name to a performance score.

        Returns:
            Standard deviation of scores across districts.
        """
        if not results_by_district:
            return 0.0
        values = list(results_by_district.values())
        return float(np.std(values))

    def test_fairness(self, results: list[dict]) -> dict:
        """Test whether model results are fair across districts.

        Args:
            results: List of dicts with keys: district (str), score (float).

        Returns:
            Dict with keys: variance, max_deviation, is_fair.
        """
        if not results:
            return {"variance": 0.0, "max_deviation": 0.0, "is_fair": True}

        scores_by_district: dict[str, list[float]] = {}
        for r in results:
            district = r["district"]
            scores_by_district.setdefault(district, []).append(r["score"])

        district_means = {d: float(np.mean(s)) for d, s in scores_by_district.items()}
        mean_values = list(district_means.values())

        overall_mean = float(np.mean(mean_values))
        variance = float(np.std(mean_values))

        deviations = [abs(v - overall_mean) for v in mean_values]
        max_deviation = float(max(deviations)) if deviations else 0.0

        # Fairness threshold from CLAUDE.md: bias std dev < 0.10
        is_fair = variance < 0.10

        return {
            "variance": variance,
            "max_deviation": max_deviation,
            "is_fair": is_fair,
        }
