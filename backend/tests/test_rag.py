"""Tests for the RAG pipeline (Phase 8A)."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.rag.ollama_client import OllamaClient
from src.services.rag.embedder import EmbeddingService
from src.services.rag.vector_store import VectorStoreService
from src.services.rag.prompts import build_context
from src.services.rag.rag_pipeline import RAGPipeline


# ──────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────

SAMPLE_DETECTIONS = [
    {
        "detection_id": str(uuid.uuid4()),
        "detection_type": "pothole",
        "confidence_score": 0.92,
        "caption": "Large pothole on EDSA near Guadalupe",
        "lat": 14.5649,
        "lon": 121.0322,
        "created_at": "2026-01-15T08:30:00",
        "distance": 0.1234,
    },
    {
        "detection_id": str(uuid.uuid4()),
        "detection_type": "sidewalk_obstruction",
        "confidence_score": 0.85,
        "caption": "Street vendor blocking sidewalk in Makati",
        "lat": 14.5547,
        "lon": 121.0244,
        "created_at": "2026-01-16T10:00:00",
        "distance": 0.2345,
    },
]


@pytest.fixture
def mock_settings():
    with patch("src.services.rag.ollama_client.get_settings") as mock:
        settings = MagicMock()
        settings.ollama_base_url = "http://localhost:11434"
        settings.ollama_model = "mistral"
        mock.return_value = settings
        yield settings


@pytest.fixture
def ollama_client(mock_settings):
    return OllamaClient()


@pytest.fixture
def embedding_service():
    with patch("src.services.rag.embedder.SentenceTransformer") as mock_st:
        import numpy as np

        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.rand(384).astype("float32")
        mock_st.return_value = mock_model
        service = EmbeddingService()
        # Force model to load with mock
        service._model = mock_model
        yield service


@pytest.fixture
def vector_store():
    session_factory = AsyncMock()
    return VectorStoreService(session_factory=session_factory)


@pytest.fixture
def rag_pipeline(ollama_client, embedding_service, vector_store):
    return RAGPipeline(
        ollama_client=ollama_client,
        embedding_service=embedding_service,
        vector_store=vector_store,
    )


# ──────────────────────────────────────────────────────────────────────
# OllamaClient tests
# ──────────────────────────────────────────────────────────────────────


class TestOllamaClient:
    def test_health_check_healthy(self, ollama_client):
        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_client.get.return_value = mock_resp
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_cls.return_value = mock_client

            assert ollama_client.health_check() is True

    def test_health_check_unhealthy(self, ollama_client):
        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.get.side_effect = Exception("Connection refused")
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_cls.return_value = mock_client

            assert ollama_client.health_check() is False

    def test_generate_returns_string(self, ollama_client):
        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"response": "There are 3 potholes detected."}
            mock_resp.raise_for_status = MagicMock()
            mock_client.post.return_value = mock_resp
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = ollama_client.generate("What potholes are nearby?")
            assert isinstance(result, str)
            assert "potholes" in result

    def test_list_models(self, ollama_client):
        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "models": [
                    {"name": "mistral"},
                    {"name": "llama2"},
                ]
            }
            mock_resp.raise_for_status = MagicMock()
            mock_client.get.return_value = mock_resp
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_cls.return_value = mock_client

            models = ollama_client.list_models()
            assert models == ["mistral", "llama2"]


# ──────────────────────────────────────────────────────────────────────
# EmbeddingService tests
# ──────────────────────────────────────────────────────────────────────


class TestEmbeddingService:
    def test_embed_text_returns_384_dim(self, embedding_service):
        import numpy as np

        embedding_service._model.encode.return_value = np.random.rand(384).astype(
            "float32"
        )
        result = embedding_service.embed_text("pothole on the road")
        assert isinstance(result, list)
        assert len(result) == 384

    def test_embed_detection(self, embedding_service):
        import numpy as np

        embedding_service._model.encode.return_value = np.random.rand(384).astype(
            "float32"
        )
        result = embedding_service.embed_detection(
            detection_type="pothole",
            location="EDSA, Makati",
            confidence=0.92,
            caption="Large pothole near Guadalupe bridge",
        )
        assert isinstance(result, list)
        assert len(result) == 384
        # Verify the model was called with a descriptive sentence
        call_args = embedding_service._model.encode.call_args
        text_arg = call_args[0][0]
        assert "pothole" in text_arg
        assert "EDSA, Makati" in text_arg


# ──────────────────────────────────────────────────────────────────────
# VectorStoreService tests
# ──────────────────────────────────────────────────────────────────────


class TestVectorStoreService:
    @pytest.mark.asyncio
    async def test_similarity_search(self):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_mappings = MagicMock()
        mock_mappings.all.return_value = [
            {
                "detection_id": str(uuid.uuid4()),
                "detection_type": "pothole",
                "confidence_score": 0.9,
                "caption": "test",
                "created_at": "2026-01-01",
                "lon": 121.0,
                "lat": 14.5,
                "distance": 0.12,
            }
        ]
        mock_result.mappings.return_value = mock_mappings
        mock_session.execute.return_value = mock_result
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        session_factory = MagicMock()
        session_factory.return_value = mock_session

        store = VectorStoreService(session_factory=session_factory)
        results = await store.similarity_search(
            query_embedding=[0.1] * 384,
            limit=5,
        )
        assert len(results) == 1
        assert results[0]["detection_type"] == "pothole"

    @pytest.mark.asyncio
    async def test_hybrid_search(self):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_mappings = MagicMock()
        mock_mappings.all.return_value = [
            {
                "detection_id": str(uuid.uuid4()),
                "detection_type": "sidewalk_obstruction",
                "confidence_score": 0.85,
                "caption": "vendor blocking path",
                "created_at": "2026-01-02",
                "lon": 121.02,
                "lat": 14.56,
                "distance": 0.15,
            }
        ]
        mock_result.mappings.return_value = mock_mappings
        mock_session.execute.return_value = mock_result
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        session_factory = MagicMock()
        session_factory.return_value = mock_session

        store = VectorStoreService(session_factory=session_factory)
        results = await store.hybrid_search(
            query_embedding=[0.1] * 384,
            lat=14.56,
            lon=121.02,
            radius_m=500.0,
            limit=5,
        )
        assert len(results) == 1
        assert results[0]["detection_type"] == "sidewalk_obstruction"


# ──────────────────────────────────────────────────────────────────────
# Prompts tests
# ──────────────────────────────────────────────────────────────────────


class TestPrompts:
    def test_build_context_with_detections(self):
        context = build_context(SAMPLE_DETECTIONS)
        assert "[1]" in context
        assert "[2]" in context
        assert "pothole" in context
        assert "sidewalk_obstruction" in context
        assert "92%" in context
        assert "EDSA" in context

    def test_build_context_empty(self):
        context = build_context([])
        assert "No relevant detections" in context


# ──────────────────────────────────────────────────────────────────────
# RAGPipeline tests
# ──────────────────────────────────────────────────────────────────────


class TestRAGPipeline:
    @pytest.mark.asyncio
    async def test_answer_query_full_flow(self, rag_pipeline):
        """Full pipeline: embed -> retrieve -> generate."""
        import numpy as np

        rag_pipeline.embedder._model.encode.return_value = np.random.rand(384).astype(
            "float32"
        )

        rag_pipeline.vector_store.similarity_search = AsyncMock(
            return_value=SAMPLE_DETECTIONS
        )

        with patch.object(
            rag_pipeline.ollama,
            "generate",
            return_value="Based on the data, there are [1] potholes and [2] obstructions in the area.",
        ):
            result = await rag_pipeline.answer_query(
                "What are the main issues near EDSA?"
            )

        assert "answer" in result
        assert "citations" in result
        assert "sources" in result
        assert isinstance(result["answer"], str)
        assert len(result["sources"]) == 2

    @pytest.mark.asyncio
    async def test_answer_query_with_spatial_filters(self, rag_pipeline):
        """Pipeline uses hybrid_search when lat/lon filters provided."""
        import numpy as np

        rag_pipeline.embedder._model.encode.return_value = np.random.rand(384).astype(
            "float32"
        )

        rag_pipeline.vector_store.hybrid_search = AsyncMock(
            return_value=SAMPLE_DETECTIONS[:1]
        )

        with patch.object(
            rag_pipeline.ollama,
            "generate",
            return_value="One pothole found [1].",
        ):
            result = await rag_pipeline.answer_query(
                "Potholes nearby?",
                filters={"lat": 14.56, "lon": 121.03, "radius_m": 500},
            )

        rag_pipeline.vector_store.hybrid_search.assert_called_once()
        assert len(result["sources"]) == 1

    def test_query_rewriting(self, rag_pipeline):
        rewritten = rag_pipeline._rewrite_query(
            "Are there pothole and ramp issues for pwd?"
        )
        assert "road surface damage" in rewritten
        assert "wheelchair accessibility" in rewritten
        assert "persons with disability" in rewritten

    @pytest.mark.asyncio
    async def test_fallback_on_ollama_failure(self, rag_pipeline):
        """When Ollama is down, return fallback answer with context."""
        import numpy as np

        rag_pipeline.embedder._model.encode.return_value = np.random.rand(384).astype(
            "float32"
        )

        rag_pipeline.vector_store.similarity_search = AsyncMock(
            return_value=SAMPLE_DETECTIONS
        )

        with patch.object(
            rag_pipeline.ollama,
            "generate",
            side_effect=Exception("Connection refused"),
        ):
            result = await rag_pipeline.answer_query("What issues exist?")

        assert "unavailable" in result["answer"]
        assert "pothole" in result["answer"]
        assert len(result["sources"]) == 2

    def test_citation_extraction(self, rag_pipeline):
        response = "The area has [1] potholes and [2] obstructions. See [1] for details."
        citations = rag_pipeline._extract_citations(response, SAMPLE_DETECTIONS)
        assert len(citations) == 2
        assert "[1]" in citations[0]
        assert "pothole" in citations[0]
        assert "[2]" in citations[1]
        assert "sidewalk_obstruction" in citations[1]

    def test_citation_extraction_no_citations(self, rag_pipeline):
        response = "No specific issues were found in the area."
        citations = rag_pipeline._extract_citations(response, SAMPLE_DETECTIONS)
        assert citations == []

    def test_citation_extraction_out_of_range(self, rag_pipeline):
        response = "See [1] and [99] for details."
        citations = rag_pipeline._extract_citations(response, SAMPLE_DETECTIONS)
        # [99] is out of range, should be ignored
        assert len(citations) == 1
        assert "[1]" in citations[0]
