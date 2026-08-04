from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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


class ChatRequest(BaseModel):
    space_id: uuid.UUID
    question: str = Field(min_length=1, max_length=4000)
    conversation_id: uuid.UUID | None = None


class ChatResponse(BaseModel):
    conversation_id: uuid.UUID
    answer: str
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
