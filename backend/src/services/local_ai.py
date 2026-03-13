"""Local CPU-based AI inference pipeline.

Runs YOLOv8n + SegFormer-B3 + BLIP-base entirely on CPU.
Models are lazy-loaded on first use (~30s initial load, then fast).
"""

from __future__ import annotations

import logging
import tempfile
import time
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Singleton model holders — loaded once, reused across requests
_yolo_model: Any = None
_seg_model: Any = None
_seg_processor: Any = None
_seg_id2label: dict = {}
_blip_model: Any = None
_blip_processor: Any = None
_models_loaded = False


# COCO class → KALYE walkability type
COCO_TO_KALYE = {
    "car": "sidewalk_obstruction",
    "truck": "sidewalk_obstruction",
    "motorcycle": "sidewalk_obstruction",
    "bicycle": "sidewalk_obstruction",
    "stop sign": "missing_sign",
    "traffic light": "missing_sign",
    "fire hydrant": "sidewalk_obstruction",
    "parking meter": "sidewalk_obstruction",
    "bench": "sidewalk_obstruction",
    "dog": "sidewalk_obstruction",
    "potted plant": "sidewalk_obstruction",
    "umbrella": "street_vendor_obstruction",
    "suitcase": "sidewalk_obstruction",
    "backpack": "sidewalk_obstruction",
}

SIDEWALK_CLASS_ID = 11
ROAD_CLASS_ID = 6


def _ensure_models():
    """Lazy-load all three models on first call."""
    global _yolo_model, _seg_model, _seg_processor, _seg_id2label
    global _blip_model, _blip_processor, _models_loaded

    if _models_loaded:
        return

    import torch
    from ultralytics import YOLO
    from transformers import (
        SegformerForSemanticSegmentation,
        SegformerImageProcessor,
        BlipForConditionalGeneration,
        BlipProcessor,
    )

    logger.info("Loading AI models (CPU) — this takes ~30s on first run...")
    start = time.time()

    # YOLOv8n — 6MB, very fast
    _yolo_model = YOLO("yolov8n.pt")
    logger.info("  YOLOv8n loaded")

    # SegFormer-B3 — 180MB
    # nosec B615 — well-known NVIDIA/Salesforce models; fallback path only (Claude Vision is primary)
    _seg_processor = SegformerImageProcessor.from_pretrained("nvidia/segformer-b3-finetuned-ade-512-512", revision="main")  # nosec B615
    _seg_model = SegformerForSemanticSegmentation.from_pretrained("nvidia/segformer-b3-finetuned-ade-512-512", revision="main")  # nosec B615
    _seg_model.eval()
    _seg_id2label = _seg_model.config.id2label
    logger.info("  SegFormer loaded (%d classes)", len(_seg_id2label))

    # BLIP-base — 990MB
    _blip_processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base", revision="main")  # nosec B615
    _blip_model = BlipForConditionalGeneration.from_pretrained(  # nosec B615
        "Salesforce/blip-image-captioning-base",
        revision="main",
    )
    _blip_model.eval()
    logger.info("  BLIP-base loaded")

    _models_loaded = True
    logger.info("All models loaded in %.1fs", time.time() - start)


def run_detection(image_path: str, confidence_threshold: float = 0.25) -> list[dict]:
    """Run YOLOv8 detection, return KALYE-format results."""
    _ensure_models()

    results = _yolo_model(image_path, verbose=False, conf=confidence_threshold)
    detections = []

    for r in results:
        if r.boxes is None:
            continue
        for i in range(len(r.boxes)):
            cls_id = int(r.boxes.cls[i].item())
            conf = float(r.boxes.conf[i].item())
            coco_name = _yolo_model.names.get(cls_id, "")
            kalye_type = COCO_TO_KALYE.get(coco_name)

            if kalye_type is None:
                continue

            xyxy = r.boxes.xyxy[i].tolist()
            detections.append({
                "detection_type": kalye_type,
                "confidence": round(conf, 3),
                "bounding_box": {
                    "x": round(xyxy[0], 1),
                    "y": round(xyxy[1], 1),
                    "w": round(xyxy[2] - xyxy[0], 1),
                    "h": round(xyxy[3] - xyxy[1], 1),
                },
                "coco_class": coco_name,
            })

    return detections


def run_segmentation(image_path: str) -> dict:
    """Run SegFormer segmentation, return sidewalk coverage stats."""
    _ensure_models()

    import torch
    import torch.nn.functional as F

    image = Image.open(image_path).convert("RGB")
    inputs = _seg_processor(images=image, return_tensors="pt")

    with torch.no_grad():
        outputs = _seg_model(**inputs)

    logits = outputs.logits
    upsampled = F.interpolate(
        logits, size=(image.height, image.width), mode="bilinear", align_corners=False
    )
    mask = upsampled.argmax(dim=1).squeeze(0).numpy()

    total_px = mask.size
    unique, counts = np.unique(mask, return_counts=True)

    class_breakdown = {}
    for cls_id, count in zip(unique, counts):
        label = _seg_id2label.get(cls_id, _seg_id2label.get(str(cls_id), f"class_{cls_id}"))
        pct = round(float(count) / total_px * 100, 2)
        if pct >= 0.5:
            class_breakdown[label] = pct

    sidewalk_px = sum(c for cid, c in zip(unique, counts) if int(cid) == SIDEWALK_CLASS_ID)
    road_px = sum(c for cid, c in zip(unique, counts) if int(cid) == ROAD_CLASS_ID)

    return {
        "sidewalk_coverage_pct": round(float(sidewalk_px) / total_px * 100, 2),
        "road_coverage_pct": round(float(road_px) / total_px * 100, 2),
        "class_breakdown": class_breakdown,
    }


def run_captioning(image_path: str) -> str:
    """Run BLIP-base captioning, return a description string."""
    _ensure_models()

    import torch

    image = Image.open(image_path).convert("RGB")
    prompt = "a photograph of a street showing"
    inputs = _blip_processor(images=image, text=prompt, return_tensors="pt")

    with torch.no_grad():
        generated_ids = _blip_model.generate(**inputs, max_new_tokens=50)

    caption = _blip_processor.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()

    if caption and caption[0].islower():
        caption = caption[0].upper() + caption[1:]
    if caption and not caption.endswith("."):
        caption += "."

    return caption


async def analyze_image_bytes(content: bytes, filename: str) -> dict:
    """Full pipeline: save to temp file, run all 3 models, return results.

    This is the main entry point called by the upload endpoint.
    Runs synchronously on CPU (~8-10s per image).
    """
    import asyncio

    suffix = ".jpg" if "jpeg" in filename.lower() or "jpg" in filename.lower() else ".png"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(content)
    tmp.close()
    tmp_path = tmp.name

    try:
        # Run in thread pool to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        start = time.time()

        detections = await loop.run_in_executor(None, run_detection, tmp_path)
        segmentation = await loop.run_in_executor(None, run_segmentation, tmp_path)
        caption = await loop.run_in_executor(None, run_captioning, tmp_path)

        elapsed = time.time() - start
        logger.info(
            "Local AI: %d detections, %.1f%% sidewalk, caption='%s' (%.1fs)",
            len(detections),
            segmentation.get("sidewalk_coverage_pct", 0),
            caption[:60],
            elapsed,
        )

        return {
            "status": "ok",
            "inference_time_seconds": round(elapsed, 2),
            "detections": detections,
            "segmentation": segmentation,
            "caption": caption,
        }
    finally:
        Path(tmp_path).unlink(missing_ok=True)
