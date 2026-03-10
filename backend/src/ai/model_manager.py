"""Singleton model manager for downloading, loading, and caching AI models."""

from __future__ import annotations

import logging
import shutil
import threading
from pathlib import Path
from typing import Any

from src.ai.model_config import MODEL_REGISTRY
from src.config.settings import get_settings

logger = logging.getLogger(__name__)


class ModelManager:
    """Thread-safe singleton that manages AI model lifecycle.

    Handles downloading from Hugging Face Hub, loading into memory,
    caching on disk, and device selection (CUDA / CPU).
    """

    _instance: ModelManager | None = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> ModelManager:
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        settings = get_settings()
        self._cache_dir = Path(settings.model_cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._hf_token: str | None = settings.hf_token or None
        self._loaded_models: dict[str, Any] = {}
        logger.info(
            "ModelManager initialized  cache_dir=%s  device=%s",
            self._cache_dir,
            self.get_device(),
        )

    # ------------------------------------------------------------------
    # Device helpers
    # ------------------------------------------------------------------

    @staticmethod
    def get_device() -> str:
        """Auto-detect the best available device (cuda or cpu)."""
        try:
            import torch

            if torch.cuda.is_available():
                return "cuda"
        except ImportError:
            logger.debug("torch not installed – defaulting to cpu")
        return "cpu"

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def download_model(self, model_id: str, revision: str = "main") -> Path:
        """Download a model from Hugging Face Hub and return its local path.

        For YOLO models (ultralytics) the weights file is downloaded via the
        ``ultralytics`` package.  All other models are fetched with the
        ``huggingface_hub`` snapshot_download helper so the full model tree
        is available for ``from_pretrained``.
        """
        logger.info("Downloading model %s (revision=%s)", model_id, revision)

        if self._is_yolo(model_id):
            return self._download_yolo(model_id)

        from huggingface_hub import snapshot_download

        local_dir = snapshot_download(
            repo_id=model_id,
            revision=revision,
            cache_dir=str(self._cache_dir),
            token=self._hf_token,
        )
        logger.info("Model downloaded to %s", local_dir)
        return Path(local_dir)

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------

    def load_model(self, model_id: str, device: str | None = None) -> Any:
        """Load a model into memory.  Returns the model object.

        Already-loaded models are returned from an in-memory cache.
        """
        if model_id in self._loaded_models:
            logger.debug("Returning cached in-memory model %s", model_id)
            return self._loaded_models[model_id]

        device = device or self.get_device()
        logger.info("Loading model %s on %s", model_id, device)

        if self._is_yolo(model_id):
            model = self._load_yolo(model_id)
        else:
            model = self._load_transformers(model_id, device)

        self._loaded_models[model_id] = model
        return model

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def get_model_path(self, model_id: str) -> Path:
        """Return the expected local cache path for *model_id*."""
        safe_name = model_id.replace("/", "--")
        return self._cache_dir / safe_name

    # ------------------------------------------------------------------
    # Integrity
    # ------------------------------------------------------------------

    def verify_model_integrity(self, model_path: Path) -> bool:
        """Check that the cached model directory exists and is non-empty."""
        if not model_path.exists():
            logger.warning("Model path does not exist: %s", model_path)
            return False
        if model_path.is_dir():
            has_files = any(model_path.iterdir())
            if not has_files:
                logger.warning("Model directory is empty: %s", model_path)
            return has_files
        # Single file (e.g. .pt weights)
        return model_path.stat().st_size > 0

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------

    def list_cached_models(self) -> list[dict]:
        """Return metadata dicts for every model present in the cache dir."""
        cached: list[dict] = []
        if not self._cache_dir.exists():
            return cached

        for entry in self._cache_dir.iterdir():
            if entry.is_dir() or entry.is_file():
                size = (
                    sum(f.stat().st_size for f in entry.rglob("*") if f.is_file())
                    if entry.is_dir()
                    else entry.stat().st_size
                )
                cached.append(
                    {
                        "name": entry.name,
                        "path": str(entry),
                        "size_bytes": size,
                    }
                )
        return cached

    def delete_model(self, model_id: str) -> bool:
        """Remove a model from the disk cache and in-memory cache."""
        self._loaded_models.pop(model_id, None)
        model_path = self.get_model_path(model_id)
        if not model_path.exists():
            logger.warning("Cannot delete – path does not exist: %s", model_path)
            return False
        if model_path.is_dir():
            shutil.rmtree(model_path)
        else:
            model_path.unlink()
        logger.info("Deleted model cache at %s", model_path)
        return True

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_yolo(model_id: str) -> bool:
        return "yolo" in model_id.lower()

    def _download_yolo(self, model_id: str) -> Path:
        from ultralytics import YOLO

        model = YOLO(model_id)
        # ultralytics downloads weights into its own cache; we just record it
        weight_path = Path(model.ckpt_path) if hasattr(model, "ckpt_path") else self.get_model_path(model_id)
        logger.info("YOLO weights at %s", weight_path)
        return weight_path

    def _load_yolo(self, model_id: str) -> Any:
        from ultralytics import YOLO

        model = YOLO(model_id)
        logger.info("YOLO model loaded: %s", model_id)
        return model

    def _load_transformers(self, model_id: str, device: str) -> Any:
        from transformers import AutoModel, AutoTokenizer

        try:
            tokenizer = AutoTokenizer.from_pretrained(
                model_id,
                cache_dir=str(self._cache_dir),
                token=self._hf_token,
            )
        except Exception:
            tokenizer = None
            logger.debug("No tokenizer for %s – skipping", model_id)

        model = AutoModel.from_pretrained(
            model_id,
            cache_dir=str(self._cache_dir),
            token=self._hf_token,
        )

        if device == "cuda":
            try:
                model = model.to(device)
            except Exception:
                logger.warning("Failed to move %s to CUDA – falling back to CPU", model_id)
                model = model.to("cpu")

        return {"model": model, "tokenizer": tokenizer}
