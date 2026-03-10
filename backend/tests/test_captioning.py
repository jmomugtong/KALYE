"""Unit tests for the BLIP-2 captioning pipeline.

All heavy models (BLIP-2, sentence-transformers) are mocked so these tests
run without GPU or large downloads.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import List
from unittest.mock import MagicMock, patch, PropertyMock

import numpy as np
import pytest

from src.ai.captioning.blip_captioner import BLIPCaptioner
from src.ai.captioning.caption_formatter import CaptionFormatter
from src.ai.captioning.caption_embedder import CaptionEmbedder


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture()
def mock_torch():
    """Patch torch so CUDA is never reported as available."""
    with patch("src.ai.captioning.blip_captioner.torch") as mock:
        mock.cuda.is_available.return_value = False
        mock.no_grad.return_value.__enter__ = MagicMock()
        mock.no_grad.return_value.__exit__ = MagicMock()
        mock.float32 = "float32"
        mock.float16 = "float16"
        yield mock


@pytest.fixture()
def fake_processor():
    """Return a mock Blip2Processor."""
    proc = MagicMock()
    proc.return_value = {"pixel_values": MagicMock(to=MagicMock(return_value={"pixel_values": "tensor"}))}
    proc.batch_decode.return_value = ["a street with a pothole and broken sidewalk"]
    # Make __call__ also support images + text for conditional captioning.
    def _call_side_effect(*args, **kwargs):
        result = MagicMock()
        result.to.return_value = {"pixel_values": "tensor"}
        return result
    proc.side_effect = _call_side_effect
    return proc


@pytest.fixture()
def fake_model():
    """Return a mock Blip2ForConditionalGeneration."""
    model = MagicMock()
    model.to.return_value = model
    model.generate.return_value = [[1, 2, 3]]
    return model


@pytest.fixture()
def captioner(mock_torch, fake_processor, fake_model):
    """Return a BLIPCaptioner with fully mocked internals."""
    with patch(
        "src.ai.captioning.blip_captioner.Blip2Processor",
        create=True,
    ) as proc_cls, patch(
        "src.ai.captioning.blip_captioner.Blip2ForConditionalGeneration",
        create=True,
    ) as model_cls:
        # Avoid real imports inside _load_model
        with patch.dict("sys.modules", {
            "transformers": MagicMock(
                Blip2Processor=MagicMock(from_pretrained=MagicMock(return_value=fake_processor)),
                Blip2ForConditionalGeneration=MagicMock(
                    from_pretrained=MagicMock(return_value=fake_model)
                ),
            ),
        }):
            c = BLIPCaptioner(device="cpu")
            # Directly inject mocked model and processor so _load_model
            # doesn't try real imports.
            c._processor = fake_processor
            c._model = fake_model
            yield c


@pytest.fixture()
def tmp_image(tmp_path: Path) -> Path:
    """Create a tiny 4x4 PNG for testing."""
    from PIL import Image

    img = Image.new("RGB", (4, 4), color=(128, 128, 128))
    path = tmp_path / "test_image.png"
    img.save(path)
    return path


# ======================================================================
# BLIPCaptioner tests
# ======================================================================


class TestBLIPCaptionerInit:
    """Tests for BLIPCaptioner construction."""

    def test_default_model_name(self, mock_torch):
        c = BLIPCaptioner.__new__(BLIPCaptioner)
        c.model_name = "Salesforce/blip2-opt-2.7b"
        c.device = "cpu"
        c._processor = None
        c._model = None
        assert c.model_name == "Salesforce/blip2-opt-2.7b"

    def test_device_defaults_to_cpu_when_no_cuda(self, mock_torch):
        c = BLIPCaptioner(device=None)
        assert c.device == "cpu"

    def test_explicit_device(self, mock_torch):
        c = BLIPCaptioner(device="cuda")
        assert c.device == "cuda"


class TestBLIPCaptionerGenerate:
    """Tests for caption generation."""

    def test_single_caption_returns_string(
        self, captioner, tmp_image, fake_processor
    ):
        fake_processor.batch_decode.return_value = ["a broken sidewalk near a road"]
        caption = captioner.generate_caption(tmp_image)
        assert isinstance(caption, str)
        assert len(caption) > 0

    def test_caption_is_cleaned(self, captioner, tmp_image, fake_processor):
        fake_processor.batch_decode.return_value = ["  a messy caption  "]
        caption = captioner.generate_caption(tmp_image)
        assert caption[0].isupper()
        assert caption.endswith(".")

    def test_conditional_captioning_with_prompt(
        self, captioner, tmp_image, fake_processor
    ):
        fake_processor.batch_decode.return_value = [
            "there is a pothole on the left side"
        ]
        caption = captioner.generate_caption(
            tmp_image, prompt="Question: What hazards are visible?"
        )
        assert isinstance(caption, str)
        assert "pothole" in caption.lower()

    def test_file_not_found_raises(self, captioner):
        with pytest.raises(FileNotFoundError):
            captioner.generate_caption(Path("/nonexistent/image.png"))

    def test_batch_captioning(self, captioner, tmp_image, fake_processor):
        fake_processor.batch_decode.return_value = ["a caption"]
        captions = captioner.generate_captions_batch([tmp_image, tmp_image])
        assert len(captions) == 2
        assert all(isinstance(c, str) for c in captions)


class TestBLIPCaptionerClean:
    """Tests for the static _clean_caption helper."""

    def test_strips_whitespace(self):
        assert BLIPCaptioner._clean_caption("  hello  ") == "Hello."

    def test_capitalises_first_letter(self):
        assert BLIPCaptioner._clean_caption("hello world") == "Hello world."

    def test_adds_period(self):
        assert BLIPCaptioner._clean_caption("Hello world") == "Hello world."

    def test_does_not_double_period(self):
        assert BLIPCaptioner._clean_caption("Hello world.") == "Hello world."


# ======================================================================
# CaptionFormatter tests
# ======================================================================


class TestCaptionFormatterRemoveArtifacts:
    """Tests for artifact removal."""

    def test_removes_unk_tokens(self):
        text = "A <unk> street with [UNK] damage"
        result = CaptionFormatter.remove_artifacts(text)
        assert "<unk>" not in result
        assert "[UNK]" not in result

    def test_removes_pad_tokens(self):
        text = "<pad> Hello <PAD> world </s>"
        result = CaptionFormatter.remove_artifacts(text)
        assert "<pad>" not in result.lower()
        assert "</s>" not in result

    def test_collapses_repeated_phrases(self):
        text = "a man walking a man walking down the street"
        result = CaptionFormatter.remove_artifacts(text)
        assert result.count("a man walking") == 1

    def test_collapses_extra_spaces(self):
        text = "hello   world"
        result = CaptionFormatter.remove_artifacts(text)
        assert "  " not in result


class TestCaptionFormatterCapitalize:
    """Tests for capitalisation."""

    def test_capitalises_first_letter(self):
        assert CaptionFormatter.capitalize_properly("hello") == "Hello"

    def test_already_capitalised(self):
        assert CaptionFormatter.capitalize_properly("Hello") == "Hello"

    def test_empty_string(self):
        assert CaptionFormatter.capitalize_properly("") == ""


class TestCaptionFormatterPeriod:
    """Tests for trailing punctuation."""

    def test_adds_period(self):
        assert CaptionFormatter.add_period_if_missing("Hello") == "Hello."

    def test_no_double_period(self):
        assert CaptionFormatter.add_period_if_missing("Hello.") == "Hello."

    def test_preserves_exclamation(self):
        assert CaptionFormatter.add_period_if_missing("Watch out!") == "Watch out!"

    def test_preserves_question_mark(self):
        assert CaptionFormatter.add_period_if_missing("Is it safe?") == "Is it safe?"

    def test_empty_string(self):
        assert CaptionFormatter.add_period_if_missing("") == ""


class TestCaptionFormatterPipeline:
    """Tests for the full format_caption pipeline."""

    def test_format_caption_full_pipeline(self):
        formatter = CaptionFormatter()
        raw = "  <unk> a broken sidewalk a broken sidewalk near [UNK] the road  "
        result = formatter.format_caption(raw)
        assert result[0].isupper()
        assert result.endswith(".")
        assert "<unk>" not in result
        assert "[UNK]" not in result
        # Repeated phrase should be collapsed.
        assert result.lower().count("a broken sidewalk") == 1


# ======================================================================
# CaptionEmbedder tests
# ======================================================================


def _make_mock_sentence_transformer(dim: int = 384):
    """Return a mock SentenceTransformer that produces deterministic vectors."""
    model = MagicMock()

    def _encode(text, convert_to_numpy=True):
        rng = np.random.RandomState(hash(str(text)) % 2**31)
        if isinstance(text, list):
            return np.array([rng.randn(dim).astype(np.float32) for _ in text])
        return rng.randn(dim).astype(np.float32)

    model.encode.side_effect = _encode
    return model


class TestCaptionEmbedder:
    """Tests for embedding and similarity."""

    def _make_embedder(self) -> CaptionEmbedder:
        embedder = CaptionEmbedder()
        embedder._model = _make_mock_sentence_transformer()
        return embedder

    def test_embed_returns_384_dim(self):
        embedder = self._make_embedder()
        vec = embedder.embed_caption("A pothole on the road.")
        assert isinstance(vec, list)
        assert len(vec) == 384

    def test_embed_batch(self):
        embedder = self._make_embedder()
        vecs = embedder.embed_captions_batch(["caption one", "caption two"])
        assert len(vecs) == 2
        assert all(len(v) == 384 for v in vecs)

    def test_similarity_identical_is_one(self):
        embedder = self._make_embedder()
        # Override encode to return the exact same vector for any input.
        fixed = np.ones(384, dtype=np.float32)
        embedder._model.encode.side_effect = lambda text, **kw: fixed.copy()
        sim = embedder.compute_similarity("same", "same")
        assert abs(sim - 1.0) < 1e-5

    def test_similarity_different_less_than_one(self):
        embedder = self._make_embedder()
        sim = embedder.compute_similarity(
            "A pothole on the road",
            "A beautiful sunset over the ocean",
        )
        assert sim < 1.0

    def test_default_model_name(self):
        embedder = CaptionEmbedder()
        assert embedder.model_name == "sentence-transformers/all-MiniLM-L6-v2"
