"""Post-processing utilities for segmentation masks."""

from __future__ import annotations

import numpy as np
from scipy.ndimage import label as ndimage_label
from scipy.ndimage import median_filter


class SegmentationPostprocessor:
    """Clean up raw segmentation masks before analysis."""

    @staticmethod
    def smooth_mask(mask: np.ndarray, kernel_size: int = 5) -> np.ndarray:
        """Apply a median filter to remove salt-and-pepper noise.

        Parameters
        ----------
        mask:
            (H, W) integer class-ID array.
        kernel_size:
            Size of the square median filter kernel (must be odd).

        Returns
        -------
        np.ndarray
            Smoothed mask with the same shape and dtype.
        """
        smoothed = median_filter(mask.astype(np.float64), size=kernel_size)
        return np.round(smoothed).astype(mask.dtype)

    @staticmethod
    def fill_holes(mask: np.ndarray, min_hole_size: int = 100) -> np.ndarray:
        """Fill small holes (connected regions of a minority class) in each
        class region.

        For every class present in *mask*, connected components of
        *other* classes that are entirely surrounded by that class and
        are smaller than *min_hole_size* pixels are reassigned to the
        surrounding class.

        Parameters
        ----------
        mask:
            (H, W) integer class-ID array.
        min_hole_size:
            Maximum number of pixels in a hole that will be filled.

        Returns
        -------
        np.ndarray
            Mask with small holes filled.
        """
        result = mask.copy()
        classes = np.unique(mask)

        for cls_id in classes:
            # Binary mask of pixels that are NOT this class
            not_cls = result != cls_id
            # Label connected components of non-class regions
            labelled, num_features = ndimage_label(not_cls)
            for comp_id in range(1, num_features + 1):
                component = labelled == comp_id
                if component.sum() < min_hole_size:
                    # Check if this component is surrounded by cls_id:
                    # none of the component pixels should touch the border
                    rows, cols = np.where(component)
                    on_border = (
                        np.any(rows == 0)
                        or np.any(rows == mask.shape[0] - 1)
                        or np.any(cols == 0)
                        or np.any(cols == mask.shape[1] - 1)
                    )
                    if not on_border:
                        result[component] = cls_id

        return result

    @staticmethod
    def extract_sidewalk_coverage(
        mask: np.ndarray,
        sidewalk_class_id: int = 11,
    ) -> float:
        """Compute the fraction of pixels classified as sidewalk.

        Parameters
        ----------
        mask:
            (H, W) integer class-ID array.
        sidewalk_class_id:
            The class ID representing sidewalk / pavement in the
            label map (default 11 for ADE20K).

        Returns
        -------
        float
            Sidewalk coverage ratio in [0.0, 1.0].
        """
        total = mask.size
        if total == 0:
            return 0.0
        return float(np.sum(mask == sidewalk_class_id) / total)
