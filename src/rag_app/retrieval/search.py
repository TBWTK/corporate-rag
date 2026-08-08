from __future__ import annotations

import re
import unicodedata
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from rag_app.db.models import Chunk, Document, DocumentStatus
from rag_app.retrieval.fusion import reciprocal_rank_fusion


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    location: str
    content: str
    score: float
    storage_path: str | None = None


@dataclass(frozen=True, slots=True)
class VisualContextSelection:
    chunks: tuple[RetrievedChunk, ...]
    clarification_question: str | None = None
    clarification_options: tuple[str, ...] = ()


_TOKEN_PATTERN = re.compile(r"[0-9A-Za-zА-Яа-яЁё]+")
_GENERIC_INSTRUCTION_TOKENS = frozenset(
    {
        "добавить",
        "для",
        "инструкция",
        "инструкции",
        "клиент",
        "мобильная",
        "мобильного",
        "мобильном",
        "мобильные",
        "мобильных",
        "настройка",
        "настройки",
        "настройку",
        "настроить",
        "почта",
        "почтового",
        "почтовый",
        "почты",
        "почту",
        "приложение",
        "приложении",
        "установка",
        "установить",
        "устройства",
        "устройстве",
        "устройств",
        "client",
    }
)
_CANONICAL_LABEL_TOKENS = {
    "ios": "iOS",
    "outlook": "Outlook",
    "teams": "Teams",
    "vmware": "VMware",
    "vpn": "VPN",
    "вкс": "ВКС",
}


def hybrid_search(
    session: Session,
    *,
    space_id: uuid.UUID,
    question: str,
    query_vector: list[float],
    candidates: int = 18,
    top_k: int = 6,
) -> list[RetrievedChunk]:
    distance = Chunk.embedding.cosine_distance(query_vector)
    vector_rows = session.execute(
        select(
            Chunk.id,
            Chunk.document_id,
            Document.filename,
            Chunk.location,
            Chunk.content,
            (1 - distance).label("raw_score"),
            Document.storage_path,
        )
        .join(Document, Document.id == Chunk.document_id)
        .where(
            Chunk.space_id == space_id,
            Document.status == DocumentStatus.READY,
        )
        .order_by(distance)
        .limit(candidates)
    ).all()

    tsvector = func.to_tsvector("russian", Chunk.content)
    tsquery = func.websearch_to_tsquery("russian", question)
    lexical_score = func.ts_rank_cd(tsvector, tsquery)
    lexical_rows = session.execute(
        select(
            Chunk.id,
            Chunk.document_id,
            Document.filename,
            Chunk.location,
            Chunk.content,
            lexical_score.label("raw_score"),
            Document.storage_path,
        )
        .join(Document, Document.id == Chunk.document_id)
        .where(
            Chunk.space_id == space_id,
            Document.status == DocumentStatus.READY,
            tsvector.op("@@")(tsquery),
        )
        .order_by(desc(lexical_score))
        .limit(candidates)
    ).all()

    details = {str(row.id): row for row in [*vector_rows, *lexical_rows]}
    fused = reciprocal_rank_fusion(
        [
            [str(row.id) for row in vector_rows],
            [str(row.id) for row in lexical_rows],
        ]
    )
    return [
        RetrievedChunk(
            id=row.id,
            document_id=row.document_id,
            filename=row.filename,
            location=row.location,
            content=row.content,
            score=score,
            storage_path=row.storage_path,
        )
        for item_id, score in fused[:top_k]
        if (row := details.get(item_id)) is not None
    ]


def select_visual_context(question: str, retrieved: list[RetrievedChunk]) -> VisualContextSelection:
    """Выбирает явно названную visual-инструкцию или запрашивает сценарий."""
    visual_documents: dict[uuid.UUID, RetrievedChunk] = {}
    for item in retrieved:
        if " · " in item.location and item.document_id not in visual_documents:
            visual_documents[item.document_id] = item
    if len(visual_documents) < 2:
        return VisualContextSelection(chunks=tuple(retrieved))

    question_tokens = _meaningful_tokens(question)
    match_scores = {
        document_id: len(question_tokens & _meaningful_tokens(item.filename))
        for document_id, item in visual_documents.items()
    }
    best_score = max(match_scores.values(), default=0)
    best_ids = [document_id for document_id, score in match_scores.items() if score == best_score]
    if best_score > 0 and len(best_ids) == 1:
        selected_id = best_ids[0]
        visual_ids = set(visual_documents)
        scoped = tuple(
            item
            for item in retrieved
            if item.document_id == selected_id or item.document_id not in visual_ids
        )
        return VisualContextSelection(chunks=scoped)

    options = tuple(
        _visual_option_label(item.filename) for item in list(visual_documents.values())[:5]
    )
    return VisualContextSelection(
        chunks=(),
        clarification_question="Какую инструкцию использовать?",
        clarification_options=options,
    )


def _meaningful_tokens(value: str) -> set[str]:
    normalized = unicodedata.normalize("NFC", value).casefold()
    return {
        token
        for token in _TOKEN_PATTERN.findall(normalized)
        if len(token) >= 3 and token not in _GENERIC_INSTRUCTION_TOKENS
    }


def _visual_option_label(filename: str) -> str:
    stem = unicodedata.normalize("NFC", Path(filename).stem).replace("_", " ")
    words = re.sub(r"\s+", " ", stem).strip().split()
    label = " ".join(_CANONICAL_LABEL_TOKENS.get(word.casefold(), word) for word in words)
    if "ios" in {word.casefold() for word in words} and "стандартная" in label.casefold():
        return "Стандартная почта iOS"
    return label


def expand_visual_context(
    session: Session,
    retrieved: list[RetrievedChunk],
    *,
    max_chunks: int = 40,
) -> list[RetrievedChunk]:
    """Добавляет шаги релевантных визуальных инструкций в исходном порядке."""
    visual_document_ids: list[uuid.UUID] = []
    for item in retrieved:
        if " · " in item.location and item.document_id not in visual_document_ids:
            visual_document_ids.append(item.document_id)
    if not visual_document_ids:
        return retrieved

    per_document = max(1, max_chunks // len(visual_document_ids))
    anchor_scores = {
        document_id: max(item.score for item in retrieved if item.document_id == document_id)
        for document_id in visual_document_ids
    }
    expanded: list[RetrievedChunk] = []
    for document_id in visual_document_ids:
        rows = session.execute(
            select(
                Chunk.id,
                Chunk.document_id,
                Document.filename,
                Chunk.location,
                Chunk.content,
                Document.storage_path,
            )
            .join(Document, Document.id == Chunk.document_id)
            .where(
                Chunk.document_id == document_id,
                Document.status == DocumentStatus.READY,
                Chunk.location.like("стр. % · %"),
            )
            .order_by(Chunk.chunk_index)
            .limit(per_document)
        ).all()
        expanded.extend(
            RetrievedChunk(
                id=row.id,
                document_id=row.document_id,
                filename=row.filename,
                location=row.location,
                content=row.content,
                score=anchor_scores[document_id],
                storage_path=row.storage_path,
            )
            for row in rows
        )

    visual_ids = set(visual_document_ids)
    other = [item for item in retrieved if item.document_id not in visual_ids]
    return [*expanded, *other][:max_chunks] if expanded else retrieved
