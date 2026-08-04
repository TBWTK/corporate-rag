from __future__ import annotations

import hashlib
import math
import re

from rag_app.providers.base import Completion


class FakeProvider:
    """Детерминированный локальный провайдер для CI и демонстрации без токенов."""

    def __init__(self, *, dimension: int = 1024) -> None:
        self.dimension = dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        tokens = re.findall(r"[\w-]+", text.casefold())
        for token in tokens or [text.casefold()]:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def generate(self, messages: list[dict[str, str]]) -> Completion:
        content = messages[-1]["content"] if messages else ""
        match = re.search(r"\[1\].*?\n(.+?)(?:\n\n|$)", content, flags=re.DOTALL)
        excerpt = match.group(1).strip()[:280] if match else "Релевантный фрагмент не найден."
        return Completion(
            text=f"Демонстрационный ответ по найденному контексту: {excerpt} [1]",
            model="fake-deterministic",
        )
