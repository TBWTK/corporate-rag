from __future__ import annotations

from sqlalchemy import Engine

from rag_app.config import Settings
from rag_app.providers.base import ModelProvider
from rag_app.providers.fake import FakeProvider
from rag_app.providers.gigachat import GigaChatProvider
from rag_app.providers.serialized import PostgresSerializedProvider


def create_provider(settings: Settings, *, engine: Engine | None = None) -> ModelProvider:
    provider_name = settings.llm_provider.casefold().strip()
    if provider_name == "fake":
        return FakeProvider(dimension=settings.embedding_dimension)
    if provider_name != "gigachat":
        raise ValueError("LLM_PROVIDER должен быть 'gigachat' или 'fake'")
    if not settings.effective_gigachat_key:
        raise ValueError("Для LLM_PROVIDER=gigachat задайте GIGACHAT_API_KEY")
    provider = GigaChatProvider(
        auth_key=settings.effective_gigachat_key,
        scope=settings.gigachat_scope,
        embedding_model=settings.embedding_model,
        generation_model=settings.generation_model,
        api_base_url=settings.gigachat_api_base_url,
        max_output_tokens=settings.generation_max_tokens,
        verify_ssl=settings.gigachat_verify_ssl,
        ca_bundle_file=settings.gigachat_ca_bundle_file,
    )
    if settings.gigachat_serialize_requests and engine is not None:
        return PostgresSerializedProvider(provider, engine)
    return provider
