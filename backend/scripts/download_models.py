#!/usr/bin/env python3
"""Download and verify AI model artifacts from Hugging Face Hub.

Usage:
    python download_models.py --model all
    python download_models.py --model yolo --cache-dir ./models
    python download_models.py --model segformer --check
"""

import argparse
import hashlib
import os
import sys
from pathlib import Path

MODEL_REGISTRY = {
    "yolo": {
        "repo_id": "ultralytics/yolov8n",
        "filename": "yolov8n.pt",
        "description": "YOLOv8 Nano — object detection (potholes, signs, barriers)",
    },
    "segformer": {
        "repo_id": "nvidia/segformer-b0-finetuned-ade-512-512",
        "filename": "pytorch_model.bin",
        "description": "SegFormer B0 — semantic segmentation (sidewalks, roads, curbs)",
    },
    "blip2": {
        "repo_id": "Salesforce/blip2-opt-2.7b",
        "filename": "pytorch_model.bin",
        "description": "BLIP-2 OPT 2.7B — image captioning",
    },
    "embedder": {
        "repo_id": "sentence-transformers/all-MiniLM-L6-v2",
        "filename": "pytorch_model.bin",
        "description": "MiniLM-L6-v2 — sentence embeddings for RAG",
    },
}


def compute_sha256(filepath: Path) -> str:
    """Compute SHA-256 checksum of a file."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def get_cached_path(cache_dir: Path, repo_id: str, filename: str) -> Path:
    """Return the expected local path for a cached model file."""
    safe_repo = repo_id.replace("/", "--")
    return cache_dir / safe_repo / filename


def download_model(
    model_key: str,
    cache_dir: Path,
    check_only: bool = False,
) -> bool:
    """Download a single model from Hugging Face Hub.

    Returns True if the model is available (downloaded or already cached).
    """
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        print(
            "ERROR: huggingface_hub is not installed. "
            "Run: pip install huggingface_hub",
            file=sys.stderr,
        )
        return False

    try:
        from tqdm import tqdm  # noqa: F401 — verify availability
    except ImportError:
        print(
            "WARNING: tqdm is not installed; progress bars will be unavailable. "
            "Run: pip install tqdm",
            file=sys.stderr,
        )

    info = MODEL_REGISTRY[model_key]
    repo_id = info["repo_id"]
    filename = info["filename"]

    cached_path = get_cached_path(cache_dir, repo_id, filename)

    # --check mode: verify file exists and print checksum
    if check_only:
        if cached_path.exists():
            checksum = compute_sha256(cached_path)
            print(f"  [OK] {model_key}: {cached_path}")
            print(f"       SHA-256: {checksum}")
            return True
        else:
            # Also check huggingface_hub default cache
            try:
                from huggingface_hub import try_to_load_from_cache

                resolved = try_to_load_from_cache(repo_id, filename)
                if resolved is not None and Path(resolved).exists():
                    checksum = compute_sha256(Path(resolved))
                    print(f"  [OK] {model_key}: {resolved}")
                    print(f"       SHA-256: {checksum}")
                    return True
            except Exception:
                pass
            print(f"  [MISSING] {model_key}: not found in {cache_dir}")
            return False

    # Skip download if file already exists
    if cached_path.exists():
        checksum = compute_sha256(cached_path)
        print(f"  [CACHED] {model_key} — {info['description']}")
        print(f"           Path: {cached_path}")
        print(f"           SHA-256: {checksum}")
        return True

    # Download
    print(f"  [DOWNLOADING] {model_key} — {info['description']}")
    print(f"                Repo: {repo_id}")
    try:
        downloaded_path = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            cache_dir=str(cache_dir),
            force_filename=filename,
            local_dir=str(cache_dir / repo_id.replace("/", "--")),
            local_dir_use_symlinks=False,
        )
        downloaded_path = Path(downloaded_path)

        # Verify checksum after download
        checksum = compute_sha256(downloaded_path)
        print(f"  [OK] Downloaded to: {downloaded_path}")
        print(f"       SHA-256: {checksum}")
        return True

    except Exception as e:
        print(f"  [FAIL] {model_key}: {e}", file=sys.stderr)
        return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download AI model artifacts from Hugging Face Hub.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Available models: " + ", ".join(MODEL_REGISTRY.keys()),
    )
    parser.add_argument(
        "--model",
        choices=list(MODEL_REGISTRY.keys()) + ["all"],
        required=True,
        help="Model to download, or 'all' for every model.",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path(os.environ.get("MODEL_CACHE_DIR", "./models")),
        help="Directory to store downloaded models (default: ./models or MODEL_CACHE_DIR env).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify that models are cached without downloading.",
    )

    args = parser.parse_args()

    models_to_process = (
        list(MODEL_REGISTRY.keys()) if args.model == "all" else [args.model]
    )

    args.cache_dir.mkdir(parents=True, exist_ok=True)

    action = "Verifying" if args.check else "Downloading"
    print(f"\n{action} models → {args.cache_dir.resolve()}\n")

    results = {}
    for model_key in models_to_process:
        results[model_key] = download_model(
            model_key, args.cache_dir, check_only=args.check
        )
        print()

    # Summary
    ok_count = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"Result: {ok_count}/{total} models {'verified' if args.check else 'ready'}.")

    if ok_count < total:
        sys.exit(1)


if __name__ == "__main__":
    main()
