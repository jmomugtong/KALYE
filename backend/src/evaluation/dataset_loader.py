"""Dataset loading utilities for model evaluation."""

from __future__ import annotations

import json
import os
from pathlib import Path


class EvaluationDatasetLoader:
    """Loads evaluation datasets in COCO format and other supported formats."""

    def __init__(self, data_dir: str = "data/evals") -> None:
        self.data_dir = Path(data_dir)

    def load_detection_dataset(self) -> list[dict]:
        """Load detection evaluation dataset in COCO format.

        Expects a file at {data_dir}/detection/annotations.json in COCO format.

        Returns:
            List of dicts with keys: image_id, file_name, annotations (list of
            dicts with bbox [x1,y1,x2,y2] and class_id).
        """
        annotations_path = self.data_dir / "detection" / "annotations.json"
        coco_data = self._load_coco_annotations(str(annotations_path))
        return self._convert_coco_to_eval_format(coco_data)

    def load_segmentation_dataset(self) -> list[dict]:
        """Load segmentation evaluation dataset.

        Expects a file at {data_dir}/segmentation/annotations.json with entries
        containing image paths and corresponding mask paths.

        Returns:
            List of dicts with keys: image_id, image_path, mask_path.
        """
        annotations_path = self.data_dir / "segmentation" / "annotations.json"
        if not annotations_path.exists():
            raise FileNotFoundError(
                f"Segmentation annotations not found at {annotations_path}"
            )
        with open(annotations_path, "r") as f:
            data = json.load(f)

        results = []
        for entry in data.get("images", []):
            results.append(
                {
                    "image_id": entry["id"],
                    "image_path": os.path.join(
                        str(self.data_dir), "segmentation", "images", entry["file_name"]
                    ),
                    "mask_path": os.path.join(
                        str(self.data_dir),
                        "segmentation",
                        "masks",
                        entry.get("mask_file", entry["file_name"].replace(".jpg", ".png")),
                    ),
                }
            )
        return results

    def load_walkability_ground_truth(self) -> dict:
        """Load walkability scoring ground truth data.

        Expects a file at {data_dir}/walkability/ground_truth.json with
        district-level walkability scores.

        Returns:
            Dict mapping district names to ground truth walkability scores and metadata.
        """
        gt_path = self.data_dir / "walkability" / "ground_truth.json"
        if not gt_path.exists():
            raise FileNotFoundError(
                f"Walkability ground truth not found at {gt_path}"
            )
        with open(gt_path, "r") as f:
            return json.load(f)

    def _load_coco_annotations(self, path: str) -> dict:
        """Load and parse a COCO-format annotation file.

        Args:
            path: Path to the COCO JSON annotation file.

        Returns:
            Parsed COCO annotation dict with keys: images, annotations, categories.
        """
        path_obj = Path(path)
        if not path_obj.exists():
            raise FileNotFoundError(f"COCO annotations not found at {path}")
        with open(path_obj, "r") as f:
            data = json.load(f)

        # Validate expected COCO keys
        for key in ("images", "annotations", "categories"):
            if key not in data:
                raise ValueError(
                    f"Invalid COCO format: missing '{key}' key in {path}"
                )
        return data

    def _convert_coco_to_eval_format(self, coco_data: dict) -> list[dict]:
        """Convert COCO annotation format to evaluation format.

        COCO bboxes are [x, y, width, height] -> convert to [x1, y1, x2, y2].

        Args:
            coco_data: Parsed COCO annotation dict.

        Returns:
            List of per-image evaluation dicts.
        """
        images_map: dict[int, dict] = {}
        for img in coco_data["images"]:
            images_map[img["id"]] = {
                "image_id": img["id"],
                "file_name": img["file_name"],
                "annotations": [],
            }

        for ann in coco_data["annotations"]:
            image_id = ann["image_id"]
            if image_id not in images_map:
                continue
            x, y, w, h = ann["bbox"]
            images_map[image_id]["annotations"].append(
                {
                    "bbox": [x, y, x + w, y + h],
                    "class_id": ann["category_id"],
                }
            )

        return list(images_map.values())
