from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TypeVar, cast

from sqlalchemy import Engine, text

from rag_app.providers.base import Completion, ModelProvider, VisionModelProvider

T = TypeVar("T")


class PostgresSerializedProvider:
    """Сериализует модельные вызовы между API и worker через advisory lock."""

    LOCK_ID = 7_321_044_991

    def __init__(self, provider: ModelProvider, engine: Engine) -> None:
        self.provider = provider
        self.engine = engine

    def _locked(self, operation: Callable[[], T]) -> T:
        with self.engine.connect() as connection:
            connection.execute(text("SELECT pg_advisory_lock(:lock_id)"), {"lock_id": self.LOCK_ID})
            try:
                return operation()
            finally:
                connection.execute(
                    text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": self.LOCK_ID}
                )

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self._locked(lambda: self.provider.embed(texts))

    def generate(self, messages: list[dict[str, str]]) -> Completion:
        return self._locked(lambda: self.provider.generate(messages))

    def analyze_image(self, image_path: Path, *, prompt: str) -> Completion:
        if not isinstance(self.provider, VisionModelProvider):
            raise TypeError("Провайдер не поддерживает анализ изображений")
        vision_provider = cast(VisionModelProvider, self.provider)
        return self._locked(lambda: vision_provider.analyze_image(image_path, prompt=prompt))

    def close(self) -> None:
        close = getattr(self.provider, "close", None)
        if callable(close):
            close()
