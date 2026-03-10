"""Evaluation metrics for semantic segmentation masks."""

from __future__ import annotations

import numpy as np


class SegmentationMetrics:
    """Compute standard segmentation quality metrics."""

    @staticmethod
    def calculate_iou(
        pred_mask: np.ndarray,
        gt_mask: np.ndarray,
        class_id: int,
    ) -> float:
        """Intersection-over-Union for a single class.

        Parameters
        ----------
        pred_mask:
            Predicted (H, W) integer class-ID mask.
        gt_mask:
            Ground-truth (H, W) integer class-ID mask.
        class_id:
            The class whose IoU should be computed.

        Returns
        -------
        float
            IoU in [0.0, 1.0].  Returns 0.0 when the class is absent
            from both masks (union is zero).
        """
        pred_bin = pred_mask == class_id
        gt_bin = gt_mask == class_id

        intersection = np.logical_and(pred_bin, gt_bin).sum()
        union = np.logical_or(pred_bin, gt_bin).sum()

        if union == 0:
            return 0.0
        return float(intersection / union)

    @staticmethod
    def calculate_coverage(mask: np.ndarray, class_id: int) -> float:
        """Fraction of *mask* pixels that belong to *class_id*.

        Returns
        -------
        float
            Coverage ratio in [0.0, 1.0].
        """
        total = mask.size
        if total == 0:
            return 0.0
        return float(np.sum(mask == class_id) / total)

    @classmethod
    def calculate_mean_iou(
        cls,
        pred_mask: np.ndarray,
        gt_mask: np.ndarray,
    ) -> float:
        """Mean IoU across all classes present in the ground-truth mask.

        Only classes that appear in at least one of the two masks are
        included so that absent classes do not dilute the score.

        Returns
        -------
        float
            Mean IoU in [0.0, 1.0].
        """
        all_classes = np.union1d(np.unique(pred_mask), np.unique(gt_mask))
        if len(all_classes) == 0:
            return 0.0

        ious = [cls.calculate_iou(pred_mask, gt_mask, int(c)) for c in all_classes]
        return float(np.mean(ious))
