"""AI model registry and configuration for KALYE inference pipeline."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelSpec:
    """Specification for a registered AI model."""

    model_id: str
    task: str
    revision: str
    description: str


MODEL_REGISTRY: dict[str, ModelSpec] = {
    "yolo_pothole": ModelSpec(
        model_id="keremberke/yolov8m-pothole-detection",
        task="object-detection",
        revision="main",
        description="YOLOv8m fine-tuned for pothole detection in street imagery",
    ),
    "segformer_sidewalk": ModelSpec(
        model_id="nvidia/segformer-b3-finetuned-ade-512-512",
        task="semantic-segmentation",
        revision="main",
        description="SegFormer B3 for sidewalk/road/curb segmentation",
    ),
    "blip2_captioner": ModelSpec(
        model_id="Salesforce/blip2-opt-2.7b",
        task="image-to-text",
        revision="main",
        description="BLIP-2 OPT 2.7B for street scene captioning",
    ),
    "vilt_vqa": ModelSpec(
        model_id="dandelin/vilt-b32-finetuned-vqa",
        task="visual-question-answering",
        revision="main",
        description="ViLT B32 for ADA compliance visual question answering",
    ),
    "embedder": ModelSpec(
        model_id="sentence-transformers/all-MiniLM-L6-v2",
        task="feature-extraction",
        revision="main",
        description="MiniLM L6 v2 sentence embeddings for RAG pipeline",
    ),
}
