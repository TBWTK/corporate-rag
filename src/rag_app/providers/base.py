from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class Completion:
    text: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0


class ModelProvider(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...

    def generate(self, messages: list[dict[str, str]]) -> Completion: ...


@runtime_checkable
class VisionModelProvider(Protocol):
    def analyze_image(self, image_path: Path, *, prompt: str) -> Completion: ...


class ProviderError(RuntimeError):
    """Безопасная ошибка внешнего модельного API."""


class ProviderSafetyError(ProviderError):
    """Модель отклонила запрос по политике безопасности."""
