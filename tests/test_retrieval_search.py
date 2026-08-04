from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

from rag_app.retrieval.search import hybrid_search


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
