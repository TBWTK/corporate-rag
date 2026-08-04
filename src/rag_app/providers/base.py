from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Completion:
    text: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0


class ModelProvider(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...

    def generate(self, messages: list[dict[str, str]]) -> Completion: ...


class ProviderError(RuntimeError):
    """Безопасная ошибка внешнего модельного API."""


class ProviderSafetyError(ProviderError):
    """Модель отклонила запрос по политике безопасности."""
