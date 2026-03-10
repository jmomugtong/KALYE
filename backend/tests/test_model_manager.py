"""Unit tests for the AI model manager and model config registry.

All external dependencies (transformers, ultralytics, torch, huggingface_hub)
are mocked so these tests run without GPU or network access.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.ai.model_config import MODEL_REGISTRY, ModelSpec
from src.ai.model_manager import ModelManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset the ModelManager singleton before each test."""
    ModelManager._instance = None
    yield
    ModelManager._instance = None


@pytest.fixture()
def tmp_cache(tmp_path: Path):
    """Provide a temporary cache dir and patch settings to use it."""
    mock_settings = MagicMock()
    mock_settings.model_cache_dir = str(tmp_path / "models")
    mock_settings.hf_token = ""

    with patch("src.ai.model_manager.get_settings", return_value=mock_settings):
        yield tmp_path / "models"


# ---------------------------------------------------------------------------
# model_config registry
# ---------------------------------------------------------------------------


class TestModelConfig:
    def test_registry_has_all_expected_keys(self):
        expected = {
            "yolo_pothole",
            "segformer_sidewalk",
            "blip2_captioner",
            "vilt_vqa",
            "embedder",
        }
        assert expected == set(MODEL_REGISTRY.keys())

    def test_all_entries_are_model_specs(self):
        for key, spec in MODEL_REGISTRY.items():
            assert isinstance(spec, ModelSpec), f"{key} is not a ModelSpec"

    @pytest.mark.parametrize(
        "key,expected_id",
        [
            ("yolo_pothole", "keremberke/yolov8m-pothole-detection"),
            ("segformer_sidewalk", "nvidia/segformer-b3-finetuned-ade-512-512"),
            ("blip2_captioner", "Salesforce/blip2-opt-2.7b"),
            ("vilt_vqa", "dandelin/vilt-b32-finetuned-vqa"),
            ("embedder", "sentence-transformers/all-MiniLM-L6-v2"),
        ],
    )
    def test_model_ids(self, key: str, expected_id: str):
        assert MODEL_REGISTRY[key].model_id == expected_id

    def test_specs_have_nonempty_descriptions(self):
        for key, spec in MODEL_REGISTRY.items():
            assert spec.description, f"{key} has empty description"

    def test_specs_have_revision(self):
        for key, spec in MODEL_REGISTRY.items():
            assert spec.revision == "main", f"{key} revision is not 'main'"


# ---------------------------------------------------------------------------
# Singleton pattern
# ---------------------------------------------------------------------------


class TestSingleton:
    def test_singleton_returns_same_instance(self, tmp_cache):
        a = ModelManager()
        b = ModelManager()
        assert a is b

    def test_singleton_reset_creates_new_instance(self, tmp_cache):
        a = ModelManager()
        ModelManager._instance = None
        b = ModelManager()
        assert a is not b


# ---------------------------------------------------------------------------
# get_device
# ---------------------------------------------------------------------------


class TestGetDevice:
    @patch("src.ai.model_manager.ModelManager.get_device", return_value="cuda")
    def test_returns_cuda_when_available(self, _mock_dev, tmp_cache):
        assert ModelManager.get_device() == "cuda"

    def test_returns_cuda_with_torch(self, tmp_cache):
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True
        with patch.dict("sys.modules", {"torch": mock_torch}):
            # Need to call the real static method
            ModelManager._instance = None
            assert ModelManager.get_device() == "cuda"

    def test_returns_cpu_when_no_cuda(self, tmp_cache):
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False
        with patch.dict("sys.modules", {"torch": mock_torch}):
            assert ModelManager.get_device() == "cpu"

    def test_fallback_to_cpu_without_torch(self, tmp_cache):
        """When torch is not installed at all, should return cpu."""
        with patch.dict("sys.modules", {"torch": None}):
            # Importing a None module raises ImportError
            result = ModelManager.get_device()
            assert result == "cpu"


# ---------------------------------------------------------------------------
# download_model
# ---------------------------------------------------------------------------


class TestDownloadModel:
    @patch("src.ai.model_manager.ModelManager.get_device", return_value="cpu")
    def test_download_transformers_model(self, _dev, tmp_cache):
        with patch("huggingface_hub.snapshot_download", return_value=str(tmp_cache / "downloaded")) as mock_dl:
            mgr = ModelManager()
            result = mgr.download_model("nvidia/segformer-b3-finetuned-ade-512-512", revision="main")

            mock_dl.assert_called_once_with(
                repo_id="nvidia/segformer-b3-finetuned-ade-512-512",
                revision="main",
                cache_dir=str(tmp_cache),
                token=None,
            )
            assert result == Path(str(tmp_cache / "downloaded"))

    @patch("src.ai.model_manager.ModelManager.get_device", return_value="cpu")
    def test_download_yolo_model(self, _dev, tmp_cache):
        mock_yolo_instance = MagicMock()
        mock_yolo_instance.ckpt_path = str(tmp_cache / "yolo.pt")

        with patch("ultralytics.YOLO", return_value=mock_yolo_instance):
            mgr = ModelManager()
            result = mgr.download_model("keremberke/yolov8m-pothole-detection")

            assert result == Path(str(tmp_cache / "yolo.pt"))


# ---------------------------------------------------------------------------
# load_model
# ---------------------------------------------------------------------------


class TestLoadModel:
    @patch("src.ai.model_manager.ModelManager.get_device", return_value="cpu")
    def test_load_yolo_model(self, _dev, tmp_cache):
        mock_yolo_cls = MagicMock()
        mock_model = MagicMock()
        mock_yolo_cls.return_value = mock_model

        with patch("ultralytics.YOLO", mock_yolo_cls):
            mgr = ModelManager()
            result = mgr.load_model("keremberke/yolov8m-pothole-detection")

            mock_yolo_cls.assert_called_once_with("keremberke/yolov8m-pothole-detection")
            assert result is mock_model

    @patch("src.ai.model_manager.ModelManager.get_device", return_value="cpu")
    def test_load_transformers_model(self, _dev, tmp_cache):
        mock_auto_model = MagicMock()
        mock_auto_tokenizer = MagicMock()
        mock_model_obj = MagicMock()
        mock_tokenizer_obj = MagicMock()
        mock_auto_model.from_pretrained.return_value = mock_model_obj
        mock_auto_tokenizer.from_pretrained.return_value = mock_tokenizer_obj

        with patch("transformers.AutoModel", mock_auto_model), patch(
            "transformers.AutoTokenizer", mock_auto_tokenizer
        ):
            mgr = ModelManager()
            result = mgr.load_model("sentence-transformers/all-MiniLM-L6-v2")

            mock_auto_model.from_pretrained.assert_called_once()
            assert result["model"] is mock_model_obj
            assert result["tokenizer"] is mock_tokenizer_obj

    @patch("src.ai.model_manager.ModelManager.get_device", return_value="cpu")
    def test_load_model_returns_cached(self, _dev, tmp_cache):
        sentinel = object()
        mgr = ModelManager()
        mgr._loaded_models["some/model"] = sentinel

        result = mgr.load_model("some/model")
        assert result is sentinel

    @patch("src.ai.model_manager.ModelManager.get_device", return_value="cpu")
    def test_load_model_cuda_fallback(self, _dev, tmp_cache):
        """If moving to CUDA fails, model should fallback to CPU."""
        mock_auto_model = MagicMock()
        mock_auto_tokenizer = MagicMock()
        mock_model_obj = MagicMock()
        mock_model_obj.to.side_effect = [RuntimeError("CUDA OOM"), mock_model_obj]
        mock_auto_model.from_pretrained.return_value = mock_model_obj
        mock_auto_tokenizer.from_pretrained.return_value = MagicMock()

        with patch("transformers.AutoModel", mock_auto_model), patch(
            "transformers.AutoTokenizer", mock_auto_tokenizer
        ):
            mgr = ModelManager()
            result = mgr.load_model("sentence-transformers/all-MiniLM-L6-v2", device="cuda")

            # Should have called .to twice: first "cuda" (fails), then "cpu"
            assert mock_model_obj.to.call_count == 2
            assert result["model"] is mock_model_obj


# ---------------------------------------------------------------------------
# list_cached_models
# ---------------------------------------------------------------------------


class TestListCachedModels:
    @patch("src.ai.model_manager.ModelManager.get_device", return_value="cpu")
    def test_empty_cache(self, _dev, tmp_cache):
        mgr = ModelManager()
        assert mgr.list_cached_models() == []

    @patch("src.ai.model_manager.ModelManager.get_device", return_value="cpu")
    def test_lists_directories_and_files(self, _dev, tmp_cache):
        mgr = ModelManager()
        cache_dir = Path(mgr._cache_dir)

        # Create a model directory with a file
        model_dir = cache_dir / "test-model"
        model_dir.mkdir(parents=True)
        (model_dir / "weights.bin").write_bytes(b"\x00" * 1024)

        # Create a standalone weights file
        (cache_dir / "standalone.pt").write_bytes(b"\x00" * 512)

        result = mgr.list_cached_models()
        names = {entry["name"] for entry in result}
        assert "test-model" in names
        assert "standalone.pt" in names
        assert len(result) == 2


# ---------------------------------------------------------------------------
# delete_model
# ---------------------------------------------------------------------------


class TestDeleteModel:
    @patch("src.ai.model_manager.ModelManager.get_device", return_value="cpu")
    def test_delete_existing_directory(self, _dev, tmp_cache):
        mgr = ModelManager()
        model_path = mgr.get_model_path("org/my-model")
        model_path.mkdir(parents=True)
        (model_path / "config.json").write_text("{}")

        assert mgr.delete_model("org/my-model") is True
        assert not model_path.exists()

    @patch("src.ai.model_manager.ModelManager.get_device", return_value="cpu")
    def test_delete_nonexistent_returns_false(self, _dev, tmp_cache):
        mgr = ModelManager()
        assert mgr.delete_model("does/not-exist") is False

    @patch("src.ai.model_manager.ModelManager.get_device", return_value="cpu")
    def test_delete_removes_from_memory_cache(self, _dev, tmp_cache):
        mgr = ModelManager()
        mgr._loaded_models["org/my-model"] = MagicMock()

        # Path doesn't exist so disk delete returns False, but memory is cleared
        mgr.delete_model("org/my-model")
        assert "org/my-model" not in mgr._loaded_models


# ---------------------------------------------------------------------------
# verify_model_integrity
# ---------------------------------------------------------------------------


class TestVerifyModelIntegrity:
    @patch("src.ai.model_manager.ModelManager.get_device", return_value="cpu")
    def test_nonexistent_path_returns_false(self, _dev, tmp_cache):
        mgr = ModelManager()
        assert mgr.verify_model_integrity(tmp_cache / "nope") is False

    @patch("src.ai.model_manager.ModelManager.get_device", return_value="cpu")
    def test_empty_directory_returns_false(self, _dev, tmp_cache):
        mgr = ModelManager()
        empty_dir = tmp_cache / "empty"
        empty_dir.mkdir(parents=True)
        assert mgr.verify_model_integrity(empty_dir) is False

    @patch("src.ai.model_manager.ModelManager.get_device", return_value="cpu")
    def test_valid_directory_returns_true(self, _dev, tmp_cache):
        mgr = ModelManager()
        model_dir = tmp_cache / "valid-model"
        model_dir.mkdir(parents=True)
        (model_dir / "weights.bin").write_bytes(b"\x00" * 100)
        assert mgr.verify_model_integrity(model_dir) is True

    @patch("src.ai.model_manager.ModelManager.get_device", return_value="cpu")
    def test_valid_file_returns_true(self, _dev, tmp_cache):
        mgr = ModelManager()
        weight_file = tmp_cache / "model.pt"
        weight_file.parent.mkdir(parents=True, exist_ok=True)
        weight_file.write_bytes(b"\x00" * 100)
        assert mgr.verify_model_integrity(weight_file) is True

    @patch("src.ai.model_manager.ModelManager.get_device", return_value="cpu")
    def test_empty_file_returns_false(self, _dev, tmp_cache):
        mgr = ModelManager()
        weight_file = tmp_cache / "empty.pt"
        weight_file.parent.mkdir(parents=True, exist_ok=True)
        weight_file.write_bytes(b"")
        assert mgr.verify_model_integrity(weight_file) is False
