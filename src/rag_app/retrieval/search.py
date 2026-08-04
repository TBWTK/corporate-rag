from __future__ import annotations

import uuid
from dataclasses import dataclass

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
        )
        for item_id, score in fused[:top_k]
        if (row := details.get(item_id)) is not None
    ]
