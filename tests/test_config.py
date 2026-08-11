from unittest.mock import Mock

import pytest

from rag_app.config import Settings
from rag_app.providers.factory import create_provider
from rag_app.providers.fake import FakeProvider
from rag_app.providers.ollama import OllamaProvider
from rag_app.providers.serialized import PostgresSerializedProvider


def test_fake_provider_can_start_without_credentials() -> None:
    settings = Settings(_env_file=None, llm_provider="fake", embedding_dimension=24)

    provider = create_provider(settings)

    assert isinstance(provider, FakeProvider)
    assert len(provider.embed(["проверка"])[0]) == 24


def test_gigachat_provider_requires_authorization_key() -> None:
    settings = Settings(
        _env_file=None,
        llm_provider="gigachat",
        gigachat_api_key=None,
        llm_api_key=None,
    )

    with pytest.raises(ValueError, match="GIGACHAT_API_KEY"):
        create_provider(settings)


def test_embedding_2_chunk_budget_is_guarded() -> None:
    with pytest.raises(ValueError, match="chunk_max_chars"):
        Settings(
            _env_file=None,
            embedding_model="Embeddings-2",
            chunk_max_chars=2000,
        )


def test_ollama_provider_can_start_without_credentials() -> None:
    settings = Settings(
        _env_file=None,
        llm_provider="ollama",
        generation_model="qwen3:8b",
        embedding_model="mxbai-embed-large",
        embedding_dimension=1024,
    )

    provider = create_provider(settings)

    assert isinstance(provider, OllamaProvider)
    assert provider.generation_model == "qwen3:8b"
    assert provider.vision_model == "qwen2.5vl:3b"
    provider.close()


def test_ollama_requires_current_pgvector_dimension() -> None:
    with pytest.raises(ValueError, match="pgvector"):
        Settings(_env_file=None, llm_provider="ollama", embedding_dimension=768)


def test_ollama_factory_serializes_shared_model_calls() -> None:
    settings = Settings(
        _env_file=None,
        llm_provider="ollama",
        generation_model="qwen3:8b",
        embedding_model="mxbai-embed-large",
    )

    provider = create_provider(settings, engine=Mock())  # type: ignore[arg-type]

    assert isinstance(provider, PostgresSerializedProvider)
    assert isinstance(provider.provider, OllamaProvider)
    provider.close()
