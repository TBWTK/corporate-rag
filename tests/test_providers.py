from __future__ import annotations

import base64
import json
import time
from pathlib import Path

import httpx
import pytest

from rag_app.providers.base import Completion
from rag_app.providers.fake import FakeProvider
from rag_app.providers.gigachat import GigaChatProvider
from rag_app.providers.ollama import OllamaProvider


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


def test_gigachat_vision_uploads_analyzes_and_deletes_image(tmp_path: Path) -> None:
    requests: list[httpx.Request] = []
    file_id = "6f0b1291-c7f3-43c6-bb2e-9f3efb2dc98e"

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/v2/oauth":
            return httpx.Response(
                200,
                json={
                    "access_token": "access-token",
                    "expires_at": int((time.time() + 1800) * 1000),
                },
            )
        assert request.headers["Authorization"] == "Bearer access-token"
        assert request.headers["X-Client-ID"] == "client-42"
        if request.url.path == "/v1/files":
            assert "multipart/form-data" in request.headers["Content-Type"]
            assert b'name="purpose"' in request.content
            assert b"general" in request.content
            assert b"page.png" in request.content
            return httpx.Response(200, json={"id": file_id})
        if request.url.path == "/v1/chat/completions":
            payload = json.loads(request.content)
            assert payload["messages"][0]["attachments"] == [file_id]
            assert payload["messages"][0]["content"] == "Разбери страницу"
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {"content": '{"page_summary":"Настройка"}'},
                            "finish_reason": "stop",
                        }
                    ],
                    "model": "GigaChat-2-Pro",
                    "usage": {"prompt_tokens": 20, "completion_tokens": 7},
                },
            )
        if request.url.path == f"/v1/files/{file_id}/delete":
            return httpx.Response(200, json={"deleted": True})
        raise AssertionError(f"Unexpected URL: {request.url}")

    image = tmp_path / "page.png"
    image.write_bytes(b"not-a-real-png-needed-for-http-test")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = GigaChatProvider(
            auth_key="auth-key",
            generation_model="GigaChat-2-Pro",
            client_id="client-42",
            client=client,
        )
        completion = provider.analyze_image(image, prompt="Разбери страницу")

    assert completion.text == '{"page_summary":"Настройка"}'
    assert completion.prompt_tokens == 20
    assert [request.url.path for request in requests] == [
        "/api/v2/oauth",
        "/v1/files",
        "/v1/chat/completions",
        f"/v1/files/{file_id}/delete",
    ]


def test_ollama_provider_embeds_and_generates_structured_answer() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        payload = json.loads(request.content)
        if request.url.path == "/api/embed":
            assert payload == {
                "model": "embed-local",
                "input": ["первый", "второй"],
                "truncate": True,
                "dimensions": 3,
                "keep_alive": "7m",
            }
            return httpx.Response(200, json={"embeddings": [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]})
        if request.url.path == "/api/chat":
            assert payload["model"] == "chat-local"
            assert payload["format"] == "json"
            assert payload["think"] is False
            assert payload["keep_alive"] == "7m"
            assert payload["options"] == {
                "temperature": 0.1,
                "num_ctx": 8192,
                "num_predict": 900,
            }
            return httpx.Response(
                200,
                json={
                    "model": "chat-local",
                    "message": {"content": '{"answer":"Ответ [1]"}'},
                    "prompt_eval_count": 21,
                    "eval_count": 8,
                },
            )
        raise AssertionError(f"Unexpected URL: {request.url}")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = OllamaProvider(
            embedding_model="embed-local",
            generation_model="chat-local",
            embedding_dimension=3,
            context_length=8192,
            keep_alive="7m",
            max_output_tokens=900,
            client=client,
        )
        vectors = provider.embed(["первый", "второй"])
        completion = provider.generate([{"role": "user", "content": "вопрос"}])

    assert vectors == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    assert completion == Completion(
        text='{"answer":"Ответ [1]"}',
        model="chat-local",
        prompt_tokens=21,
        completion_tokens=8,
    )
    assert [request.url.path for request in requests] == ["/api/embed", "/api/chat"]


def test_ollama_provider_lists_models_and_analyzes_image(tmp_path: Path) -> None:
    image_payload = b"local-image"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(
                200,
                json={"models": [{"name": "qwen3:8b"}, {"name": "qwen2.5vl:3b"}]},
            )
        payload = json.loads(request.content)
        assert request.url.path == "/api/chat"
        assert payload["model"] == "qwen2.5vl:3b"
        assert payload["options"]["temperature"] == 0.0
        assert base64.b64decode(payload["messages"][0]["images"][0]) == image_payload
        return httpx.Response(
            200,
            json={
                "model": "qwen2.5vl:3b",
                "message": {"content": '{"page_summary":"Настройка"}'},
                "prompt_eval_count": 30,
                "eval_count": 11,
            },
        )

    image = tmp_path / "page.png"
    image.write_bytes(image_payload)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = OllamaProvider(client=client)
        assert provider.available_models() == ["qwen3:8b", "qwen2.5vl:3b"]
        completion = provider.analyze_image(image, prompt="Разбери страницу")

    assert completion.model == "qwen2.5vl:3b"
    assert completion.text == '{"page_summary":"Настройка"}'
    assert completion.prompt_tokens == 30


@pytest.mark.parametrize(
    ("status_code", "message"),
    [(404, "ollama pull"), (503, "памяти"), (500, "HTTP 500")],
)
def test_ollama_provider_surfaces_safe_errors(status_code: int, message: str) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"error": "secret-local-path"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = OllamaProvider(embedding_dimension=3, client=client)
        with pytest.raises(RuntimeError, match=message) as error:
            provider.embed(["текст"])

    assert "secret-local-path" not in str(error.value)


def test_ollama_provider_rejects_wrong_embedding_shape() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embeddings": [[0.1, 0.2]]})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = OllamaProvider(embedding_dimension=3, client=client)
        with pytest.raises(RuntimeError, match="размерности 3"):
            provider.embed(["текст"])


def test_ollama_provider_hides_connection_details() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("secret-host-path", request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = OllamaProvider(embedding_dimension=3, client=client)
        with pytest.raises(RuntimeError, match="Не удалось подключиться") as error:
            provider.embed(["текст"])

    assert "secret-host-path" not in str(error.value)
