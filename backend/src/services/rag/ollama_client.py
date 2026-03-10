"""Ollama LLM client for local model inference."""

from __future__ import annotations

import logging
from typing import AsyncGenerator, List

import httpx

from src.config.settings import get_settings

logger = logging.getLogger(__name__)


class OllamaClient:
    """HTTP client for the Ollama REST API."""

    def __init__(self, base_url: str | None = None) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.default_model = settings.ollama_model
        self._timeout = httpx.Timeout(120.0, connect=10.0)

    # ------------------------------------------------------------------
    # Health & discovery
    # ------------------------------------------------------------------

    def health_check(self) -> bool:
        """Return True if the Ollama server is reachable."""
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
        except Exception as exc:
            logger.warning("Ollama health check failed: %s", exc)
            return False

    def list_models(self) -> List[str]:
        """Return names of models available on the Ollama server."""
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(f"{self.base_url}/api/tags")
                resp.raise_for_status()
                data = resp.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception as exc:
            logger.error("Failed to list Ollama models: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def generate(
        self,
        prompt: str,
        model: str | None = None,
        stream: bool = False,
        temperature: float = 0.3,
        max_tokens: int = 500,
    ) -> str:
        """Send a prompt to Ollama and return the full generated text."""
        model = model or self.default_model
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": stream,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                )
                resp.raise_for_status()
                return resp.json().get("response", "")
        except Exception as exc:
            logger.error("Ollama generate failed: %s", exc)
            raise

    async def agenerate_stream(
        self,
        prompt: str,
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 500,
    ) -> AsyncGenerator[str, None]:
        """Stream tokens from Ollama as an async generator."""
        model = model or self.default_model
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/generate",
                json=payload,
            ) as resp:
                resp.raise_for_status()
                import json as _json

                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk = _json.loads(line)
                        token = chunk.get("response", "")
                        if token:
                            yield token
                        if chunk.get("done", False):
                            break
                    except _json.JSONDecodeError:
                        continue
