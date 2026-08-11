from __future__ import annotations

from dataclasses import dataclass

from rag_app.config import Settings, get_settings
from rag_app.providers.base import ProviderError
from rag_app.providers.factory import create_provider
from rag_app.providers.ollama import OllamaProvider


class LocalCheckError(RuntimeError):
    """Понятная оператору ошибка проверки локального контура."""


@dataclass(frozen=True, slots=True)
class LocalCheckResult:
    models: tuple[str, ...]
    embedding_dimension: int
    generation_model: str
    vision_model: str | None


def _normalized_model_name(name: str) -> str:
    return name.removesuffix(":latest")


def run_local_check(
    settings: Settings,
    *,
    provider: OllamaProvider | None = None,
) -> LocalCheckResult:
    if settings.llm_provider.casefold().strip() != "ollama":
        raise LocalCheckError("В .env должно быть RAG_LLM_PROVIDER=ollama")
    resolved_provider = provider or create_provider(settings)
    if not isinstance(resolved_provider, OllamaProvider):
        raise LocalCheckError("Factory не создал Ollama provider")
    owns_provider = provider is None
    try:
        available = resolved_provider.available_models()
        normalized_available = {_normalized_model_name(name) for name in available}
        required = {settings.generation_model, settings.embedding_model}
        if settings.vision_ingestion_enabled:
            required.add(settings.ollama_vision_model)
        missing = sorted(
            model for model in required if _normalized_model_name(model) not in normalized_available
        )
        if missing:
            commands = ", ".join(f"ollama pull {model}" for model in missing)
            raise LocalCheckError(
                f"Не загружены модели: {', '.join(missing)}. Выполните: {commands}"
            )

        vectors = resolved_provider.embed(["Локальная проверка корпоративного поиска"])
        if not vectors or len(vectors[0]) != settings.embedding_dimension:
            raise LocalCheckError(
                f"Ожидался embedding размерности {settings.embedding_dimension}"
            )
        completion = resolved_provider.generate(
            [
                {
                    "role": "system",
                    "content": "Верни только JSON: {\"status\": \"ok\"}.",
                },
                {"role": "user", "content": "Проверь локальную генерацию."},
            ]
        )
        if not completion.text:
            raise LocalCheckError("Локальная chat-модель вернула пустой ответ")
        return LocalCheckResult(
            models=tuple(available),
            embedding_dimension=len(vectors[0]),
            generation_model=completion.model,
            vision_model=(
                settings.ollama_vision_model if settings.vision_ingestion_enabled else None
            ),
        )
    finally:
        if owns_provider:
            resolved_provider.close()


def main() -> None:
    try:
        result = run_local_check(get_settings())
    except (LocalCheckError, ProviderError, ValueError) as error:
        raise SystemExit(f"LOCAL CHECK FAILED: {error}") from error
    print("LOCAL CHECK OK")
    print(f"Models: {', '.join(result.models)}")
    print(f"Embedding dimension: {result.embedding_dimension}")
    print(f"Generation model: {result.generation_model}")
    print(f"Vision model: {result.vision_model or 'disabled'}")


if __name__ == "__main__":
    main()
