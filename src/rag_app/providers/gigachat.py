from __future__ import annotations

import ssl
import time
import uuid
from mimetypes import guess_type
from pathlib import Path
from typing import Any

import httpx

from rag_app.providers.base import Completion, ProviderError, ProviderSafetyError


class GigaChatProvider:
    AUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"

    def __init__(
        self,
        *,
        auth_key: str,
        scope: str = "GIGACHAT_API_PERS",
        embedding_model: str = "Embeddings-2",
        generation_model: str = "GigaChat-2-Pro",
        api_base_url: str = "https://api.giga.chat/v1",
        timeout_seconds: float = 60.0,
        max_output_tokens: int = 1200,
        vision_max_output_tokens: int = 2400,
        client_id: str | None = None,
        verify_ssl: bool = True,
        ca_bundle_file: str | Path | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        if not auth_key.strip():
            raise ValueError("GIGACHAT_API_KEY не задан")
        self.auth_key = auth_key.removeprefix("Basic ").strip()
        self.scope = scope
        self.embedding_model = embedding_model
        self.generation_model = generation_model
        self.api_base_url = api_base_url.rstrip("/")
        self.max_output_tokens = max_output_tokens
        self.vision_max_output_tokens = vision_max_output_tokens
        self.client_id = client_id.strip() if client_id and client_id.strip() else None
        verify: bool | ssl.SSLContext = verify_ssl
        if verify_ssl and ca_bundle_file is not None:
            context = ssl.create_default_context()
            context.load_verify_locations(cafile=str(ca_bundle_file))
            verify = context
        self._client = client or httpx.Client(timeout=timeout_seconds, verify=verify)
        self._owns_client = client is None
        self._access_token: str | None = None
        self._token_expires_at = 0.0

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def _get_access_token(self) -> str:
        now = time.time()
        if self._access_token and now < self._token_expires_at - 30:
            return self._access_token
        try:
            response = self._client.post(
                self.AUTH_URL,
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Basic {self.auth_key}",
                    "RqUID": str(uuid.uuid4()),
                },
                data={"scope": self.scope},
            )
        except httpx.HTTPError as error:
            raise ProviderError("Не удалось подключиться к сервису авторизации GigaChat") from error
        if response.status_code in {400, 401, 403}:
            raise ProviderError("Ошибка авторизации GigaChat: проверьте API key и scope")
        try:
            response.raise_for_status()
            payload = response.json()
            token = str(payload["access_token"])
            expires_at = float(payload["expires_at"])
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise ProviderError("GigaChat вернул некорректный ответ авторизации") from error
        if expires_at > 10_000_000_000:
            expires_at /= 1000
        self._access_token = token
        self._token_expires_at = expires_at
        return token

    def _headers(self, token: str) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        if self.client_id:
            headers["X-Client-ID"] = self.client_id
        return headers

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        token = self._get_access_token()
        try:
            response = self._client.post(
                f"{self.api_base_url}{path}",
                headers=self._headers(token),
                json=payload,
            )
        except httpx.HTTPError as error:
            raise ProviderError("Не удалось подключиться к GigaChat API") from error
        return self._parse_response(response)

    def _upload_file(self, path: Path) -> str:
        token = self._get_access_token()
        media_type = guess_type(path.name)[0] or "application/octet-stream"
        try:
            with path.open("rb") as stream:
                response = self._client.post(
                    f"{self.api_base_url}/files",
                    headers=self._headers(token),
                    data={"purpose": "general"},
                    files={"file": (path.name, stream, media_type)},
                )
        except (OSError, httpx.HTTPError) as error:
            raise ProviderError("Не удалось загрузить изображение в GigaChat") from error
        payload = self._parse_response(response)
        file_id = payload.get("id")
        if not isinstance(file_id, str):
            raise ProviderError("GigaChat не вернул идентификатор загруженного изображения")
        try:
            uuid.UUID(file_id)
        except ValueError as error:
            raise ProviderError("GigaChat вернул некорректный идентификатор файла") from error
        return file_id

    def _delete_file(self, file_id: str) -> None:
        self._post(f"/files/{file_id}/delete", {})

    def _parse_response(self, response: httpx.Response) -> dict[str, Any]:
        if response.status_code == 401:
            self._access_token = None
            raise ProviderError("Ошибка авторизации GigaChat: access token отклонён")
        if response.status_code == 429:
            raise ProviderError("GigaChat временно ограничил частоту запросов; повторите позже")
        if response.status_code == 422:
            raise ProviderError("GigaChat отклонил размер или параметры запроса")
        try:
            response.raise_for_status()
            result = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise ProviderError(
                f"GigaChat API вернул ошибку HTTP {response.status_code}"
            ) from error
        if not isinstance(result, dict):
            raise ProviderError("GigaChat API вернул неожиданный формат ответа")
        return result

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        payload = self._post("/embeddings", {"model": self.embedding_model, "input": texts})
        try:
            ordered = sorted(payload["data"], key=lambda item: item["index"])
            vectors = [[float(value) for value in item["embedding"]] for item in ordered]
        except (KeyError, TypeError, ValueError) as error:
            raise ProviderError("GigaChat вернул некорректные эмбеддинги") from error
        if len(vectors) != len(texts):
            raise ProviderError("Количество эмбеддингов не совпало с количеством текстов")
        return vectors

    def generate(self, messages: list[dict[str, str]]) -> Completion:
        payload = self._post(
            "/chat/completions",
            {
                "model": self.generation_model,
                "messages": messages,
                "temperature": 0.1,
                "max_tokens": self.max_output_tokens,
                "stream": False,
            },
        )
        try:
            choice = payload["choices"][0]
            if choice.get("finish_reason") == "blacklist":
                raise ProviderSafetyError("GigaChat отклонил запрос по политике безопасности")
            usage = payload.get("usage", {})
            return Completion(
                text=str(choice["message"]["content"]).strip(),
                model=str(payload.get("model", self.generation_model)),
                prompt_tokens=int(usage.get("prompt_tokens", 0)),
                completion_tokens=int(usage.get("completion_tokens", 0)),
            )
        except ProviderSafetyError:
            raise
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise ProviderError("GigaChat вернул некорректный ответ модели") from error

    def analyze_image(self, image_path: Path, *, prompt: str) -> Completion:
        file_id = self._upload_file(image_path)
        try:
            payload = self._post(
                "/chat/completions",
                {
                    "model": self.generation_model,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt,
                            "attachments": [file_id],
                        }
                    ],
                    "temperature": 0.0,
                    "max_tokens": self.vision_max_output_tokens,
                    "stream": False,
                },
            )
            try:
                choice = payload["choices"][0]
                if choice.get("finish_reason") == "blacklist":
                    raise ProviderSafetyError(
                        "GigaChat отклонил страницу по политике безопасности"
                    )
                usage = payload.get("usage", {})
                return Completion(
                    text=str(choice["message"]["content"]).strip(),
                    model=str(payload.get("model", self.generation_model)),
                    prompt_tokens=int(usage.get("prompt_tokens", 0)),
                    completion_tokens=int(usage.get("completion_tokens", 0)),
                )
            except ProviderSafetyError:
                raise
            except (KeyError, IndexError, TypeError, ValueError) as error:
                raise ProviderError(
                    "GigaChat вернул некорректный разбор изображения"
                ) from error
        finally:
            self._delete_file(file_id)
