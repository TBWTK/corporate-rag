from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from sqlalchemy import Engine, text

from rag_app.providers.base import Completion, ModelProvider

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

    def close(self) -> None:
        close = getattr(self.provider, "close", None)
        if callable(close):
            close()
