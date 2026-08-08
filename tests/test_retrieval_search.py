from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

from rag_app.retrieval.search import (
    RetrievedChunk,
    expand_visual_context,
    hybrid_search,
    select_visual_context,
)


class Result:
    def __init__(self, rows: list[Any]) -> None:
        self.rows = rows

    def all(self) -> list[Any]:
        return self.rows


class SearchSession:
    def __init__(self, *rankings: list[Any]) -> None:
        self.rankings = list(rankings)

    def execute(self, _statement: object) -> Result:
        return Result(self.rankings.pop(0))


def row(chunk_id: uuid.UUID, filename: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=chunk_id,
        document_id=uuid.uuid4(),
        filename=filename,
        location="стр. 1",
        content=f"Контекст {filename}",
        raw_score=0.9,
        storage_path=f"/data/{filename}",
    )


def test_hybrid_search_fuses_vector_and_lexical_rankings() -> None:
    vector_only, both, lexical_only = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    session = SearchSession(
        [row(vector_only, "vector.md"), row(both, "both.md")],
        [row(both, "both.md"), row(lexical_only, "lexical.md")],
    )

    results = hybrid_search(
        session,  # type: ignore[arg-type]
        space_id=uuid.uuid4(),
        question="точный лимит",
        query_vector=[0.1] * 1024,
        candidates=5,
        top_k=2,
    )

    assert [result.filename for result in results] == ["both.md", "vector.md"]
    assert results[0].score > results[1].score


def test_hybrid_search_handles_empty_results() -> None:
    assert (
        hybrid_search(
            SearchSession([], []),  # type: ignore[arg-type]
            space_id=uuid.uuid4(),
            question="ничего",
            query_vector=[0.0] * 1024,
        )
        == []
    )


def test_expand_visual_context_preserves_instruction_order() -> None:
    document_id = uuid.uuid4()
    native_id, link_id, first_id, second_id, other_id = (
        uuid.uuid4(),
        uuid.uuid4(),
        uuid.uuid4(),
        uuid.uuid4(),
        uuid.uuid4(),
    )
    visual_rows = [
        SimpleNamespace(
            id=native_id,
            document_id=document_id,
            filename="guide.pdf",
            location="текст",
            content="После ввода данных нажмите OK; появится сообщение об успешном подключении",
            storage_path="/data/guide.pdf",
        ),
        SimpleNamespace(
            id=link_id,
            document_id=document_id,
            filename="guide.pdf",
            location="внешние ссылки",
            content="Installer: https://downloads.example/installer.zip",
            storage_path="/data/guide.pdf",
        ),
        SimpleNamespace(
            id=first_id,
            document_id=document_id,
            filename="guide.pdf",
            location="стр. 1 · шаг 1",
            content="Откройте настройки",
            storage_path="/data/guide.pdf",
        ),
        SimpleNamespace(
            id=second_id,
            document_id=document_id,
            filename="guide.pdf",
            location="стр. 2 · шаг 2",
            content="Введите адрес сервера",
            storage_path="/data/guide.pdf",
        ),
    ]
    anchor = RetrievedChunk(
        id=second_id,
        document_id=document_id,
        filename="guide.pdf",
        location="стр. 2 · шаг 2",
        content="Введите адрес сервера",
        score=0.05,
        storage_path="/data/guide.pdf",
    )
    other = RetrievedChunk(
        id=other_id,
        document_id=uuid.uuid4(),
        filename="policy.md",
        location="раздел 1",
        content="Общее правило",
        score=0.02,
    )

    expanded = expand_visual_context(
        SearchSession(visual_rows),  # type: ignore[arg-type]
        [anchor, other],
        max_chunks=6,
    )

    assert [item.id for item in expanded] == [
        native_id,
        link_id,
        first_id,
        second_id,
        other_id,
    ]


def test_select_visual_context_requests_choice_for_ambiguous_instructions() -> None:
    ios_id, outlook_id = uuid.uuid4(), uuid.uuid4()
    retrieved = [
        RetrievedChunk(
            id=uuid.uuid4(),
            document_id=ios_id,
            filename="Стандартная почта IOS.pdf",
            location="стр. 1 · шаг 1",
            content="Откройте настройки iOS",
            score=0.05,
        ),
        RetrievedChunk(
            id=uuid.uuid4(),
            document_id=outlook_id,
            filename="Настройка почты мобильные устройства Outlook.pdf",
            location="стр. 1 · шаг 1",
            content="Откройте Outlook",
            score=0.04,
        ),
    ]

    selection = select_visual_context("Настройка почты на мобильных устройствах", retrieved)

    assert selection.clarification_question == "Какую инструкцию использовать?"
    assert selection.clarification_options == (
        "Стандартная почта iOS",
        "Настройка почты мобильные устройства Outlook",
    )
    assert selection.chunks == ()


def test_select_visual_context_keeps_explicit_outlook_instruction() -> None:
    ios_id, outlook_id, policy_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    ios = RetrievedChunk(
        id=uuid.uuid4(),
        document_id=ios_id,
        filename="Стандартная почта IOS.pdf",
        location="стр. 1 · шаг 1",
        content="Откройте настройки iOS",
        score=0.05,
    )
    outlook = RetrievedChunk(
        id=uuid.uuid4(),
        document_id=outlook_id,
        filename="Настройка почты мобильные устройства Outlook.pdf",
        location="стр. 1 · шаг 1",
        content="Откройте Outlook",
        score=0.04,
    )
    policy = RetrievedChunk(
        id=uuid.uuid4(),
        document_id=policy_id,
        filename="email-policy.md",
        location="раздел 1",
        content="Общее правило",
        score=0.02,
    )

    selection = select_visual_context("Покажи настройку Outlook", [ios, outlook, policy])

    assert selection.clarification_question is None
    assert selection.clarification_options == ()
    assert selection.chunks == (outlook, policy)
