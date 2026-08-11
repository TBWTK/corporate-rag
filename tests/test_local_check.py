from __future__ import annotations

import json

import httpx
import pytest

from rag_app.config import Settings
from rag_app.local_check import LocalCheckError, run_local_check
from rag_app.providers.ollama import OllamaProvider


def local_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "llm_provider": "ollama",
        "generation_model": "qwen3:8b",
        "embedding_model": "mxbai-embed-large",
        "embedding_dimension": 1024,
        "ollama_vision_model": "qwen2.5vl:3b",
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def test_local_check_verifies_models_embedding_and_chat() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(
                200,
                json={
                    "models": [
                        {"name": "qwen3:8b"},
                        {"name": "mxbai-embed-large:latest"},
                        {"name": "qwen2.5vl:3b"},
                    ]
                },
            )
        payload = json.loads(request.content)
        if request.url.path == "/api/embed":
            assert payload["dimensions"] == 1024
            return httpx.Response(200, json={"embeddings": [[0.0] * 1024]})
        assert request.url.path == "/api/chat"
        return httpx.Response(
            200,
            json={"model": "qwen3:8b", "message": {"content": '{"status":"ok"}'}},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = OllamaProvider(client=client)
        result = run_local_check(local_settings(), provider=provider)

    assert result.embedding_dimension == 1024
    assert result.generation_model == "qwen3:8b"
    assert result.vision_model == "qwen2.5vl:3b"


def test_local_check_reports_missing_model_commands() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": [{"name": "qwen3:8b"}]})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = OllamaProvider(client=client)
        with pytest.raises(LocalCheckError, match="ollama pull mxbai-embed-large"):
            run_local_check(local_settings(), provider=provider)


def test_local_check_requires_ollama_mode() -> None:
    with pytest.raises(LocalCheckError, match="RAG_LLM_PROVIDER=ollama"):
        run_local_check(Settings(_env_file=None, llm_provider="fake"))


def test_local_check_skips_vision_model_when_disabled() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(
                200,
                json={
                    "models": [
                        {"name": "qwen3:8b"},
                        {"name": "mxbai-embed-large:latest"},
                    ]
                },
            )
        if request.url.path == "/api/embed":
            return httpx.Response(200, json={"embeddings": [[0.0] * 1024]})
        return httpx.Response(
            200,
            json={"model": "qwen3:8b", "message": {"content": '{"status":"ok"}'}},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = OllamaProvider(client=client)
        result = run_local_check(
            local_settings(vision_ingestion_enabled=False),
            provider=provider,
        )

    assert result.vision_model is None
