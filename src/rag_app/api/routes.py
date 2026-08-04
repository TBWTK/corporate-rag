from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import suppress
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from rag_app.api.schemas import (
    ChatRequest,
    ChatResponse,
    DocumentRead,
    MessageRead,
    SpaceCreate,
    SpaceRead,
    UploadResult,
)
from rag_app.db.models import Conversation, Document, DocumentStatus, KnowledgeSpace, Message
from rag_app.db.session import database_is_ready
from rag_app.ingestion.extractors import SUPPORTED_EXTENSIONS
from rag_app.providers.base import ProviderError
from rag_app.services.chat import ChatService, ChatValidationError
from rag_app.services.ingestion import (
    DuplicateDocumentError,
    SpaceNotFoundError,
    UploadService,
    UploadValidationError,
)

router = APIRouter(prefix="/api")


def get_session(request: Request) -> Iterator[Session]:
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


SessionDependency = Annotated[Session, Depends(get_session)]


@router.get("/health")
def health(request: Request) -> dict[str, object]:
    database_ready = database_is_ready(request.app.state.engine)
    provider_ready = request.app.state.provider is not None
    return {
        "status": "ok" if database_ready and provider_ready else "degraded",
        "database": database_ready,
        "provider": request.app.state.settings.llm_provider,
        "provider_configured": provider_ready,
    }


@router.get("/config")
def public_config(request: Request) -> dict[str, object]:
    settings = request.app.state.settings
    return {
        "app_name": settings.app_name,
        "supported_extensions": sorted(SUPPORTED_EXTENSIONS),
        "max_upload_mb": settings.max_upload_mb,
        "generation_model": settings.generation_model,
        "embedding_model": settings.embedding_model,
    }


@router.get("/spaces", response_model=list[SpaceRead])
def list_spaces(session: SessionDependency) -> list[SpaceRead]:
    rows = session.execute(
        select(KnowledgeSpace, func.count(Document.id).label("document_count"))
        .outerjoin(Document, Document.space_id == KnowledgeSpace.id)
        .group_by(KnowledgeSpace.id)
        .order_by(KnowledgeSpace.created_at)
    ).all()
    return [
        SpaceRead(
            id=space.id,
            name=space.name,
            description=space.description,
            created_at=space.created_at,
            document_count=document_count,
        )
        for space, document_count in rows
    ]


@router.post("/spaces", response_model=SpaceRead, status_code=status.HTTP_201_CREATED)
def create_space(payload: SpaceCreate, session: SessionDependency) -> SpaceRead:
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Название не должно быть пустым")
    space = KnowledgeSpace(name=name, description=payload.description.strip())
    session.add(space)
    session.commit()
    session.refresh(space)
    return SpaceRead.model_validate(space)


@router.get("/spaces/{space_id}/documents", response_model=list[DocumentRead])
def list_documents(space_id: uuid.UUID, session: SessionDependency) -> list[Document]:
    if session.get(KnowledgeSpace, space_id) is None:
        raise HTTPException(status_code=404, detail="Пространство знаний не найдено")
    return list(
        session.scalars(
            select(Document)
            .where(Document.space_id == space_id)
            .order_by(Document.created_at.desc())
        )
    )


@router.post(
    "/spaces/{space_id}/documents",
    response_model=UploadResult,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_documents(
    request: Request,
    space_id: uuid.UUID,
    files: Annotated[list[UploadFile], File()],
) -> UploadResult:
    if not files:
        raise HTTPException(status_code=422, detail="Выберите хотя бы один файл")
    service = UploadService(request.app.state.settings, request.app.state.session_factory)
    queued: list[Document] = []
    duplicates: list[Document] = []
    for uploaded in files:
        payload = await uploaded.read(request.app.state.settings.max_upload_bytes + 1)
        try:
            queued.append(
                service.queue(
                    space_id=space_id,
                    filename=uploaded.filename or "document",
                    media_type=uploaded.content_type,
                    payload=payload,
                )
            )
        except DuplicateDocumentError as error:
            duplicates.append(error.document)
        except SpaceNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except UploadValidationError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        finally:
            await uploaded.close()
    return UploadResult(
        documents=[DocumentRead.model_validate(item) for item in queued],
        duplicates=[DocumentRead.model_validate(item) for item in duplicates],
    )


@router.post("/documents/{document_id}/retry", response_model=DocumentRead)
def retry_document(document_id: uuid.UUID, session: SessionDependency) -> Document:
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Документ не найден")
    document.status = DocumentStatus.QUEUED
    document.error = None
    document.processing_started_at = None
    session.commit()
    session.refresh(document)
    return document


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: uuid.UUID, session: SessionDependency) -> None:
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Документ не найден")
    storage_parent = Path(document.storage_path).parent
    session.execute(delete(Document).where(Document.id == document_id))
    session.commit()
    path = Path(document.storage_path)
    path.unlink(missing_ok=True)
    with suppress(OSError):
        storage_parent.rmdir()


@router.post("/chat", response_model=ChatResponse)
def chat(request: Request, payload: ChatRequest) -> ChatResponse:
    service = ChatService(
        request.app.state.settings,
        request.app.state.session_factory,
        request.app.state.provider,
    )
    try:
        answer = service.answer(
            space_id=payload.space_id,
            question=payload.question,
            conversation_id=payload.conversation_id,
        )
    except ChatValidationError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ProviderError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    return ChatResponse(
        conversation_id=answer.conversation_id,
        answer=answer.answer,
        response_type=answer.response_type,
        clarification_options=answer.clarification_options,
        sources=answer.sources,
        model=answer.model,
        usage=answer.usage,
    )


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageRead])
def conversation_messages(conversation_id: uuid.UUID, session: SessionDependency) -> list[Message]:
    if session.get(Conversation, conversation_id) is None:
        raise HTTPException(status_code=404, detail="Диалог не найден")
    return list(
        session.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
    )
