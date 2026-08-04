from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from rag_app.config import Settings
from rag_app.db.models import Conversation, Document, DocumentStatus, KnowledgeSpace, Message
from rag_app.generation.prompting import SourceContext, build_grounded_messages
from rag_app.providers.base import ModelProvider
from rag_app.retrieval.search import hybrid_search


class ChatValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ChatAnswer:
    conversation_id: uuid.UUID
    answer: str
    sources: list[dict[str, Any]]
    model: str
    usage: dict[str, int]


class ChatService:
    def __init__(
        self,
        settings: Settings,
        session_factory: sessionmaker[Session],
        provider: ModelProvider,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.provider = provider

    def answer(
        self,
        *,
        space_id: uuid.UUID,
        question: str,
        conversation_id: uuid.UUID | None = None,
    ) -> ChatAnswer:
        clean_question = question.strip()
        if not clean_question:
            raise ChatValidationError("Введите вопрос")
        if len(clean_question) > 4000:
            raise ChatValidationError("Вопрос должен быть короче 4000 символов")

        with self.session_factory() as session:
            space = session.get(KnowledgeSpace, space_id)
            if space is None:
                raise ChatValidationError("Пространство знаний не найдено")
            ready_count = session.scalar(
                select(func.count(Document.id)).where(
                    Document.space_id == space_id,
                    Document.status == DocumentStatus.READY,
                )
            )
            if not ready_count:
                raise ChatValidationError("Сначала загрузите и дождитесь индексации документов")
            conversation, history = self._resolve_conversation(
                session, space_id=space_id, conversation_id=conversation_id
            )
            resolved_conversation_id = conversation.id

        query_vector = self.provider.embed([clean_question])[0]
        with self.session_factory() as session:
            retrieved = hybrid_search(
                session,
                space_id=space_id,
                question=clean_question,
                query_vector=query_vector,
                candidates=self.settings.retrieval_candidates,
                top_k=self.settings.retrieval_top_k,
            )

        contexts = [
            SourceContext(
                number=index,
                filename=item.filename,
                location=item.location,
                text=item.content,
            )
            for index, item in enumerate(retrieved, start=1)
        ]
        completion = self.provider.generate(
            build_grounded_messages(clean_question, contexts, history=history)
        )
        sources = [
            {
                "number": index,
                "document_id": str(item.document_id),
                "filename": item.filename,
                "location": item.location,
                "excerpt": item.content[:500],
                "score": round(item.score, 6),
            }
            for index, item in enumerate(retrieved, start=1)
        ]

        with self.session_factory() as session, session.begin():
            session.add_all(
                [
                    Message(
                        conversation_id=resolved_conversation_id,
                        role="user",
                        content=clean_question,
                        sources=[],
                    ),
                    Message(
                        conversation_id=resolved_conversation_id,
                        role="assistant",
                        content=completion.text,
                        sources=sources,
                    ),
                ]
            )
        return ChatAnswer(
            conversation_id=resolved_conversation_id,
            answer=completion.text,
            sources=sources,
            model=completion.model,
            usage={
                "prompt_tokens": completion.prompt_tokens,
                "completion_tokens": completion.completion_tokens,
            },
        )

    def _resolve_conversation(
        self,
        session: Session,
        *,
        space_id: uuid.UUID,
        conversation_id: uuid.UUID | None,
    ) -> tuple[Conversation, list[dict[str, str]]]:
        if conversation_id is None:
            conversation = Conversation(space_id=space_id)
            session.add(conversation)
            session.commit()
            session.refresh(conversation)
            return conversation, []
        existing = session.get(Conversation, conversation_id)
        if existing is None or existing.space_id != space_id:
            raise ChatValidationError("Диалог не найден в выбранном пространстве")
        recent = list(
            session.scalars(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at.desc())
                .limit(6)
            )
        )
        history = [
            {"role": message.role, "content": message.content} for message in reversed(recent)
        ]
        return existing, history
