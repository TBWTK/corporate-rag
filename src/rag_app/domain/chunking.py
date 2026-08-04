from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TextChunk:
    index: int
    text: str
    location: str


def _normalise(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _preferred_break(text: str, start: int, hard_end: int, max_chars: int) -> int:
    if hard_end == len(text):
        return hard_end
    search_from = start + max_chars // 2
    paragraph_break = text.rfind("\n\n", search_from, hard_end)
    sentence_breaks = [text.rfind(marker, search_from, hard_end) for marker in (". ", "! ", "? ")]
    word_break = text.rfind(" ", search_from, hard_end)
    candidate = max([paragraph_break, word_break, *sentence_breaks])
    if candidate <= start:
        return hard_end
    if text[candidate : candidate + 2] in {". ", "! ", "? "}:
        return candidate + 1
    return candidate


def chunk_text(
    text: str,
    *,
    max_chars: int = 1200,
    overlap_chars: int = 180,
    location: str = "текст",
) -> list[TextChunk]:
    """Разбивает текст на ограниченные чанки с перекрытием по границе слов."""
    if max_chars < 32:
        raise ValueError("max_chars должен быть не меньше 32")
    if overlap_chars < 0 or overlap_chars >= max_chars:
        raise ValueError("overlap_chars должен быть от 0 до max_chars - 1")

    normalised = _normalise(text)
    if not normalised:
        return []

    parts: list[str] = []
    start = 0
    while start < len(normalised):
        hard_end = min(start + max_chars, len(normalised))
        end = _preferred_break(normalised, start, hard_end, max_chars)
        piece = normalised[start:end].strip()
        if piece:
            parts.append(piece)
        if end >= len(normalised):
            break

        next_start = max(start + 1, end - overlap_chars)
        while next_start > start + 1 and not normalised[next_start - 1].isspace():
            next_start -= 1
        start = next_start if next_start > start else end

    return [
        TextChunk(index=index, text=part, location=location) for index, part in enumerate(parts)
    ]
