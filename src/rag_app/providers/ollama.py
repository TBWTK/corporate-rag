from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import httpx

from rag_app.providers.base import Completion, ProviderError


class OllamaProvider:
    """Локальные embeddings, chat и vision через нативный Ollama API."""

    def __init__(
        self,
        *,
        embedding_model: str = "mxbai-embed-large",
        generation_model: str = "qwen3:8b",
        vision_model: str = "qwen2.5vl:3b",
        embedding_dimension: int = 1024,
        base_url: str = "http://host.docker.internal:11434",
        timeout_seconds: float = 600.0,
        max_output_tokens: int = 1200,
        vision_max_output_tokens: int = 2400,
        context_length: int = 16384,
        keep_alive: str = "5m",
        json_mode: bool = True,
        think: bool = False,
        client: httpx.Client | None = None,
    ) -> None:
        self.embedding_model = embedding_model
        self.generation_model = generation_model
        self.vision_model = vision_model
        self.embedding_dimension = embedding_dimension
        self.base_url = base_url.rstrip("/")
        self.max_output_tokens = max_output_tokens
        self.vision_max_output_tokens = vision_max_output_tokens
        self.context_length = context_length
        self.keep_alive = keep_alive
        self.json_mode = json_mode
        self.think = think
        self._client = client or httpx.Client(timeout=timeout_seconds)
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = self._client.request(method, f"{self.base_url}{path}", **kwargs)
        except httpx.HTTPError as error:
            raise ProviderError(
                "Не удалось подключиться к Ollama. Проверьте, что приложение запущено и "
                "OLLAMA_BASE_URL доступен из Docker."
            ) from error
        if response.status_code == 404:
            raise ProviderError(
                "Ollama не нашёл настроенную модель. Выполните ollama pull для моделей из .env."
            )
        if response.status_code == 503:
            raise ProviderError(
                "Ollama перегружен или модели не хватает памяти; дождитесь очереди либо выберите "
                "модель меньшего размера."
            )
        try:
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise ProviderError(f"Ollama API вернул ошибку HTTP {response.status_code}") from error
        if not isinstance(payload, dict):
            raise ProviderError("Ollama API вернул неожиданный формат ответа")
        return payload

    def available_models(self) -> list[str]:
        payload = self._request("GET", "/api/tags")
        try:
            return [str(model["name"]) for model in payload["models"]]
        except (KeyError, TypeError) as error:
            raise ProviderError("Ollama вернул некорректный список моделей") from error

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        payload = self._request(
            "POST",
            "/api/embed",
            json={
                "model": self.embedding_model,
                "input": texts,
                "truncate": True,
                "dimensions": self.embedding_dimension,
                "keep_alive": self.keep_alive,
            },
        )
        try:
            vectors = [
                [float(value) for value in embedding] for embedding in payload["embeddings"]
            ]
        except (KeyError, TypeError, ValueError) as error:
            raise ProviderError("Ollama вернул некорректные embeddings") from error
        if len(vectors) != len(texts):
            raise ProviderError("Количество embeddings не совпало с количеством текстов")
        if any(len(vector) != self.embedding_dimension for vector in vectors):
            raise ProviderError(
                f"Ollama вернул embedding не размерности {self.embedding_dimension}"
            )
        return vectors

    def _chat_payload(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        max_tokens: int,
        temperature: float,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "think": self.think,
            "keep_alive": self.keep_alive,
            "options": {
                "temperature": temperature,
                "num_ctx": self.context_length,
                "num_predict": max_tokens,
            },
        }
        if self.json_mode:
            payload["format"] = "json"
        return payload

    def _completion_from_payload(self, payload: dict[str, Any], *, model: str) -> Completion:
        try:
            return Completion(
                text=str(payload["message"]["content"]).strip(),
                model=str(payload.get("model", model)),
                prompt_tokens=int(payload.get("prompt_eval_count", 0)),
                completion_tokens=int(payload.get("eval_count", 0)),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ProviderError("Ollama вернул некорректный ответ модели") from error

    def generate(self, messages: list[dict[str, str]]) -> Completion:
        payload = self._request(
            "POST",
            "/api/chat",
            json=self._chat_payload(
                model=self.generation_model,
                messages=messages,
                max_tokens=self.max_output_tokens,
                temperature=0.1,
            ),
        )
        return self._completion_from_payload(payload, model=self.generation_model)

    def analyze_image(self, image_path: Path, *, prompt: str) -> Completion:
        try:
            image = base64.b64encode(image_path.read_bytes()).decode("ascii")
        except OSError as error:
            raise ProviderError("Не удалось прочитать страницу для Ollama Vision") from error
        payload = self._request(
            "POST",
            "/api/chat",
            json=self._chat_payload(
                model=self.vision_model,
                messages=[{"role": "user", "content": prompt, "images": [image]}],
                max_tokens=self.vision_max_output_tokens,
                temperature=0.0,
            ),
        )
        return self._completion_from_payload(payload, model=self.vision_model)
