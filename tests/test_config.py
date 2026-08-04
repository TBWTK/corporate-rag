import pytest

from rag_app.config import Settings
from rag_app.providers.factory import create_provider
from rag_app.providers.fake import FakeProvider


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
