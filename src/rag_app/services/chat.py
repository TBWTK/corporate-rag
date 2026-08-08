from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from rag_app.config import Settings
from rag_app.db.models import Conversation, Document, DocumentStatus, KnowledgeSpace, Message
from rag_app.generation.prompting import SourceContext, build_grounded_messages
from rag_app.generation.response import ResponseType, parse_model_response
from rag_app.ingestion.visual import page_image_path, page_number_from_location
from rag_app.providers.base import ModelProvider
from rag_app.retrieval.relations import expand_related_context
from rag_app.retrieval.search import (
    RetrievedChunk,
    expand_visual_context,
    hybrid_search,
    select_visual_context,
)


class ChatValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ChatAnswer:
    conversation_id: uuid.UUID
    answer: str
    response_type: ResponseType
    clarification_options: list[str]
    sources: list[dict[str, Any]]
    model: str
    usage: dict[str, int]


@dataclass(frozen=True, slots=True)
class CitedSourceGroup:
    citation_numbers: tuple[int, ...]
    items: tuple[RetrievedChunk, ...]


_CITATION_PATTERN = re.compile(r"\[(\d+)]")


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

        retrieval_query = _build_retrieval_query(clean_question, history)
        query_vector = self.provider.embed([retrieval_query])[0]
        with self.session_factory() as session:
            retrieved = hybrid_search(
                session,
                space_id=space_id,
                question=retrieval_query,
                query_vector=query_vector,
                candidates=self.settings.retrieval_candidates,
                top_k=self.settings.retrieval_top_k,
            )
            selection = select_visual_context(clean_question, retrieved)
            if selection.clarification_question is not None:
                self._persist_messages(
                    conversation_id=resolved_conversation_id,
                    question=clean_question,
                    answer=selection.clarification_question,
                    sources=[],
                )
                return ChatAnswer(
                    conversation_id=resolved_conversation_id,
                    answer=selection.clarification_question,
                    response_type="clarification",
                    clarification_options=list(selection.clarification_options),
                    sources=[],
                    model="visual-scenario-router",
                    usage={"prompt_tokens": 0, "completion_tokens": 0},
                )
            retrieved = expand_visual_context(
                session,
                list(selection.chunks),
                max_chunks=self.settings.visual_context_max_chunks,
            )
            retrieved = expand_related_context(
                session,
                space_id=space_id,
                query_vector=query_vector,
                retrieved=retrieved,
                max_documents=self.settings.relation_max_documents,
                chunks_per_document=self.settings.relation_chunks_per_document,
            )

        contexts = [
            SourceContext(
                number=index,
                filename=item.filename,
                location=item.location,
                text=item.content,
                relation=item.relation.description if item.relation else None,
            )
            for index, item in enumerate(retrieved, start=1)
        ]
        completion = self.provider.generate(
            build_grounded_messages(clean_question, contexts, history=history)
        )
        model_response = parse_model_response(completion.text)
        sources = (
            self._build_sources(
                retrieved,
                model_response.text,
            )
            if model_response.response_type == "answer"
            else []
        )

        self._persist_messages(
            conversation_id=resolved_conversation_id,
            question=clean_question,
            answer=model_response.text,
            sources=sources,
        )
        return ChatAnswer(
            conversation_id=resolved_conversation_id,
            answer=model_response.text,
            response_type=model_response.response_type,
            clarification_options=model_response.options,
            sources=sources,
            model=completion.model,
            usage={
                "prompt_tokens": completion.prompt_tokens,
                "completion_tokens": completion.completion_tokens,
            },
        )

    def _build_sources(self, retrieved: list[RetrievedChunk], answer: str) -> list[dict[str, Any]]:
        sources: list[dict[str, Any]] = []
        for group in _cited_source_groups(answer, retrieved):
            item = group.items[0]
            page_number = page_number_from_location(item.location)
            location = f"стр. {page_number}" if page_number is not None else item.location
            source: dict[str, Any] = {
                "number": group.citation_numbers[0],
                "citation_numbers": list(group.citation_numbers),
                "document_id": str(item.document_id),
                "filename": item.filename,
                "location": location,
                "excerpt": _source_group_excerpt(group.items),
                "score": round(max(chunk.score for chunk in group.items), 6),
            }
            if page_number is not None and item.storage_path:
                image_path = page_image_path(Path(item.storage_path), page_number)
                if image_path.is_file():
                    source["image_url"] = f"/api/documents/{item.document_id}/pages/{page_number}"
            relation = next((chunk.relation for chunk in group.items if chunk.relation), None)
            if relation is not None:
                source["relation"] = relation.as_dict()
            sources.append(source)
        return sources

    def _persist_messages(
        self,
        *,
        conversation_id: uuid.UUID,
        question: str,
        answer: str,
        sources: list[dict[str, Any]],
    ) -> None:
        with self.session_factory() as session, session.begin():
            session.add_all(
                [
                    Message(
                        conversation_id=conversation_id,
                        role="user",
                        content=question,
                        sources=[],
                    ),
                    Message(
                        conversation_id=conversation_id,
                        role="assistant",
                        content=answer,
                        sources=sources,
                    ),
                ]
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


def _build_retrieval_query(question: str, history: list[dict[str, str]]) -> str:
    relevant_history = [
        message["content"].strip() for message in history[-2:] if message.get("content", "").strip()
    ]
    return "\n".join([*relevant_history, question]).strip()


def _cited_source_groups(answer: str, retrieved: list[RetrievedChunk]) -> list[CitedSourceGroup]:
    cited_numbers: list[int] = []
    for match in _CITATION_PATTERN.finditer(answer):
        number = int(match.group(1))
        if 1 <= number <= len(retrieved) and number not in cited_numbers:
            cited_numbers.append(number)

    grouped: dict[tuple[object, ...], list[tuple[int, RetrievedChunk]]] = {}
    for number in cited_numbers:
        item = retrieved[number - 1]
        page_number = page_number_from_location(item.location)
        key: tuple[object, ...]
        if page_number is not None:
            key = ("page", item.document_id, page_number)
        else:
            key = ("chunk", item.id)
        grouped.setdefault(key, []).append((number, item))

    return [
        CitedSourceGroup(
            citation_numbers=tuple(sorted(number for number, _item in values)),
            items=tuple(item for _number, item in sorted(values)),
        )
        for values in grouped.values()
    ]


def _source_group_excerpt(items: tuple[RetrievedChunk, ...]) -> str:
    preferred_prefixes = (
        "Раздел:",
        "Назначение страницы:",
        "Шаг ",
        "Элемент интерфейса:",
        "Ввести или выбрать:",
        "Ожидаемый результат:",
        "Предупреждение:",
    )
    lines: list[str] = []
    for item in items:
        for raw_line in item.content.splitlines():
            line = raw_line.strip()
            if line.startswith(preferred_prefixes) and line not in lines:
                lines.append(line)
    fallback = items[0].content.strip() if items else ""
    return ("\n".join(lines) or fallback)[:700]
