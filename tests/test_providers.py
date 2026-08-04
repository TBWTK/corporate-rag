from __future__ import annotations

import time

import httpx
import pytest

from rag_app.providers.base import Completion
from rag_app.providers.fake import FakeProvider
from rag_app.providers.gigachat import GigaChatProvider


def test_fake_provider_is_deterministic_and_normalized() -> None:
    provider = FakeProvider(dimension=32)

    first, second = provider.embed(["политика отпусков", "политика отпусков"])

    assert first == second
    assert len(first) == 32
    assert sum(value * value for value in first) == pytest.approx(1.0)
    assert provider.generate([{"role": "user", "content": "вопрос"}]).text


def test_gigachat_provider_caches_oauth_and_sends_model_payloads() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/v2/oauth":
            assert request.headers["Authorization"] == "Basic auth-key"
            assert "scope=GIGACHAT_API_PERS" in request.content.decode()
            return httpx.Response(
                200,
                json={
                    "access_token": "access-token",
                    "expires_at": int((time.time() + 1800) * 1000),
                },
            )
        assert request.headers["Authorization"] == "Bearer access-token"
        if request.url.path == "/v1/embeddings":
            assert b'"model":"Embeddings-2"' in request.content
            return httpx.Response(
                200,
                json={
                    "data": [{"embedding": [0.1, 0.2], "index": 0}],
                    "model": "Embeddings-2",
                    "usage": {"prompt_tokens": 2},
                },
            )
        if request.url.path == "/v1/chat/completions":
            assert b'"model":"GigaChat-2-Pro"' in request.content
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "Ответ [1]"}, "finish_reason": "stop"}],
                    "model": "GigaChat-2-Pro",
                    "usage": {"prompt_tokens": 10, "completion_tokens": 3},
                },
            )
        raise AssertionError(f"Unexpected URL: {request.url}")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = GigaChatProvider(
            auth_key="auth-key",
            scope="GIGACHAT_API_PERS",
            embedding_model="Embeddings-2",
            generation_model="GigaChat-2-Pro",
            client=client,
        )
        assert provider.embed(["текст"]) == [[0.1, 0.2]]
        assert provider.embed(["ещё текст"]) == [[0.1, 0.2]]
        completion = provider.generate([{"role": "user", "content": "вопрос"}])

    assert completion == Completion(
        text="Ответ [1]",
        model="GigaChat-2-Pro",
        prompt_tokens=10,
        completion_tokens=3,
    )
    assert [request.url.path for request in requests].count("/api/v2/oauth") == 1


def test_gigachat_provider_surfaces_safe_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "bad credentials"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = GigaChatProvider(auth_key="secret", client=client)
        with pytest.raises(RuntimeError, match="авторизац") as error:
            provider.embed(["текст"])

    assert "secret" not in str(error.value)
