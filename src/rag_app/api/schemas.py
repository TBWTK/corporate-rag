from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from rag_app.db.models import DocumentRelationStatus, DocumentRelationType


class SpaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)


class SpaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str
    created_at: datetime
    document_count: int = 0


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    space_id: uuid.UUID
    filename: str
    media_type: str
    status: str
    error: str | None
    chunk_count: int
    created_at: datetime
    updated_at: datetime


class UploadResult(BaseModel):
    documents: list[DocumentRead]
    duplicates: list[DocumentRead]


class DocumentRelationCreate(BaseModel):
    source_document_id: uuid.UUID
    target_document_id: uuid.UUID
    relation_type: DocumentRelationType
    evidence: str = Field(min_length=1, max_length=1000)

    @field_validator("evidence")
    @classmethod
    def normalize_evidence(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Укажите основание связи")
        return normalized

    @model_validator(mode="after")
    def reject_self_link(self) -> DocumentRelationCreate:
        if self.source_document_id == self.target_document_id:
            raise ValueError("Документ нельзя связать с самим собой")
        return self


class DocumentRelationRead(BaseModel):
    id: uuid.UUID
    space_id: uuid.UUID
    source_document_id: uuid.UUID
    source_filename: str
    target_document_id: uuid.UUID
    target_filename: str
    relation_type: DocumentRelationType
    status: DocumentRelationStatus
    evidence: str
    created_by: str
    created_at: datetime


class ChatRequest(BaseModel):
    space_id: uuid.UUID
    question: str = Field(min_length=1, max_length=4000)
    conversation_id: uuid.UUID | None = None


class ChatResponse(BaseModel):
    conversation_id: uuid.UUID
    answer: str
    response_type: Literal["answer", "clarification"] = "answer"
    clarification_options: list[str] = Field(default_factory=list)
    sources: list[dict[str, Any]]
    model: str
    usage: dict[str, int]


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    sources: list[dict[str, Any]]
    created_at: datetime
