from __future__ import annotations

import os

import pytest

from rag_app.config import Settings
from rag_app.generation.prompting import SourceContext, build_grounded_messages
from rag_app.providers.gigachat import GigaChatProvider


@pytest.mark.live
def test_real_gigachat_embedding_and_grounded_answer() -> None:
    if os.getenv("RUN_LIVE_GIGACHAT") != "1":
        pytest.skip("Set RUN_LIVE_GIGACHAT=1 to consume GigaChat tokens")
    settings = Settings()
    assert settings.effective_gigachat_key
    provider = GigaChatProvider(
        auth_key=settings.effective_gigachat_key,
        scope=settings.gigachat_scope,
        embedding_model=settings.embedding_model,
        generation_model=settings.generation_model,
        api_base_url=settings.gigachat_api_base_url,
        max_output_tokens=128,
        verify_ssl=settings.gigachat_verify_ssl,
        ca_bundle_file=settings.gigachat_ca_bundle_file,
    )
    try:
        vector = provider.embed(["Тестовый регламент: код проверки — Альфа-17."])[0]
        completion = provider.generate(
            build_grounded_messages(
                "Какой код проверки?",
                [
                    SourceContext(
                        number=1,
                        filename="synthetic-test.txt",
                        location="строка 1",
                        text="Тестовый регламент: код проверки — Альфа-17.",
                    )
                ],
            )
        )
    finally:
        provider.close()

    assert len(vector) == settings.embedding_dimension
    assert "Альфа-17" in completion.text
    assert "[1]" in completion.text
    assert completion.prompt_tokens > 0
