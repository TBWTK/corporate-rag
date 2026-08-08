from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, aliased

from rag_app.db.models import (
    Chunk,
    Document,
    DocumentRelation,
    DocumentRelationStatus,
    DocumentRelationType,
    DocumentStatus,
)
from rag_app.retrieval.search import RetrievedChunk

RELATION_TYPE_LABELS: dict[DocumentRelationType, str] = {
    DocumentRelationType.SUPPLEMENTS: "дополняет",
    DocumentRelationType.AMENDS: "изменяет",
    DocumentRelationType.SUPERSEDES: "заменяет",
    DocumentRelationType.IMPLEMENTS: "реализует требования",
    DocumentRelationType.REFERENCES: "ссылается на",
    DocumentRelationType.ATTACHMENT_TO: "является приложением к",
}


@dataclass(frozen=True, slots=True)
class RelationProvenance:
    id: uuid.UUID
    relation_type: DocumentRelationType
    source_document_id: uuid.UUID
    source_filename: str
    target_document_id: uuid.UUID
    target_filename: str
    evidence: str

    @property
    def description(self) -> str:
        label = RELATION_TYPE_LABELS[self.relation_type]
        return f"{self.source_filename} {label} {self.target_filename}"

    def as_dict(self) -> dict[str, str]:
        return {
            "id": str(self.id),
            "type": self.relation_type.value,
            "source_document_id": str(self.source_document_id),
            "source_filename": self.source_filename,
            "target_document_id": str(self.target_document_id),
            "target_filename": self.target_filename,
            "evidence": self.evidence,
        }


def expand_related_context(
    session: Session,
    *,
    space_id: uuid.UUID,
    query_vector: list[float],
    retrieved: list[RetrievedChunk],
    max_documents: int = 3,
    chunks_per_document: int = 2,
) -> list[RetrievedChunk]:
    """Добавляет релевантные chunks подтверждённых соседей, сохраняя hybrid seeds."""
    if not retrieved or max_documents < 1 or chunks_per_document < 1:
        return retrieved

    seed_ids = list(dict.fromkeys(item.document_id for item in retrieved))
    source_document = aliased(Document)
    target_document = aliased(Document)
    relation_rows = session.execute(
        select(
            DocumentRelation.id.label("relation_id"),
            DocumentRelation.source_document_id,
            DocumentRelation.target_document_id,
            DocumentRelation.relation_type,
            DocumentRelation.status.label("relation_status"),
            DocumentRelation.evidence,
            source_document.filename.label("source_filename"),
            target_document.filename.label("target_filename"),
        )
        .join(source_document, source_document.id == DocumentRelation.source_document_id)
        .join(target_document, target_document.id == DocumentRelation.target_document_id)
        .where(
            DocumentRelation.space_id == space_id,
            DocumentRelation.status == DocumentRelationStatus.CONFIRMED,
            source_document.space_id == space_id,
            target_document.space_id == space_id,
            source_document.status == DocumentStatus.READY,
            target_document.status == DocumentStatus.READY,
            or_(
                DocumentRelation.source_document_id.in_(seed_ids),
                DocumentRelation.target_document_id.in_(seed_ids),
            ),
        )
        .order_by(DocumentRelation.created_at, DocumentRelation.id)
        .limit(max(12, max_documents * 8))
    ).all()

    seed_set = set(seed_ids)
    related_documents: list[tuple[uuid.UUID, RelationProvenance]] = []
    seen_related: set[uuid.UUID] = set()
    for row in relation_rows:
        if str(row.relation_status) != DocumentRelationStatus.CONFIRMED:
            continue
        if row.source_document_id in seed_set and row.target_document_id not in seed_set:
            related_id = row.target_document_id
        elif row.target_document_id in seed_set and row.source_document_id not in seed_set:
            related_id = row.source_document_id
        else:
            continue
        if related_id in seen_related:
            continue
        relation_type = DocumentRelationType(str(row.relation_type))
        related_documents.append(
            (
                related_id,
                RelationProvenance(
                    id=row.relation_id,
                    relation_type=relation_type,
                    source_document_id=row.source_document_id,
                    source_filename=row.source_filename,
                    target_document_id=row.target_document_id,
                    target_filename=row.target_filename,
                    evidence=row.evidence,
                ),
            )
        )
        seen_related.add(related_id)
        if len(related_documents) >= max_documents:
            break

    expanded = list(retrieved)
    seen_chunks = {item.id for item in retrieved}
    for document_id, relation in related_documents:
        distance = Chunk.embedding.cosine_distance(query_vector)
        rows = session.execute(
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
                Chunk.document_id == document_id,
                Document.space_id == space_id,
                Document.status == DocumentStatus.READY,
            )
            .order_by(distance, Chunk.chunk_index)
            .limit(chunks_per_document)
        ).all()
        for row in rows:
            if row.id in seen_chunks:
                continue
            expanded.append(
                RetrievedChunk(
                    id=row.id,
                    document_id=row.document_id,
                    filename=row.filename,
                    location=row.location,
                    content=row.content,
                    score=float(row.raw_score),
                    storage_path=row.storage_path,
                    relation=relation,
                )
            )
            seen_chunks.add(row.id)
    return expanded
