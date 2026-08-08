from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from rag_app.api.routes import router
from rag_app.config import Settings
from rag_app.db.models import (
    Document,
    DocumentRelationStatus,
    DocumentRelationType,
    DocumentStatus,
    KnowledgeSpace,
)
from rag_app.providers.fake import FakeProvider
from rag_app.retrieval.relations import RelationProvenance, expand_related_context
from rag_app.retrieval.search import RetrievedChunk
from rag_app.services.chat import ChatService


@pytest.fixture
def relation_app(tmp_path: Path, sqlite_factory: sessionmaker[Session]) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.state.settings = Settings(
        _env_file=None,
        llm_provider="fake",
        data_dir=tmp_path / "uploads",
    )
    app.state.session_factory = sqlite_factory
    app.state.engine = sqlite_factory.kw["bind"]
    app.state.provider = FakeProvider()
    return app


def _space(factory: sessionmaker[Session], name: str = "Правовые документы") -> KnowledgeSpace:
    with factory() as session, session.begin():
        space = KnowledgeSpace(name=name)
        session.add(space)
    return space


def _document(
    factory: sessionmaker[Session],
    root: Path,
    space_id: uuid.UUID,
    filename: str,
    *,
    status: DocumentStatus = DocumentStatus.READY,
) -> Document:
    document_id = uuid.uuid4()
    directory = root / str(document_id)
    directory.mkdir(parents=True)
    path = directory / filename
    path.write_text(filename, encoding="utf-8")
    with factory() as session, session.begin():
        document = Document(
            id=document_id,
            space_id=space_id,
            filename=filename,
            media_type="text/plain",
            storage_path=str(path),
            sha256=uuid.uuid4().hex,
            status=status,
        )
        session.add(document)
    return document


def test_relation_api_validates_lists_and_deletes_confirmed_links(
    relation_app: FastAPI, tmp_path: Path
) -> None:
    client = TestClient(relation_app)
    factory = relation_app.state.session_factory
    space = _space(factory)
    base = _document(factory, tmp_path, space.id, "ФЗ-1.txt")
    supplement = _document(factory, tmp_path, space.id, "ДС-к-ФЗ-1.txt")
    queued = _document(
        factory,
        tmp_path,
        space.id,
        "черновик.txt",
        status=DocumentStatus.QUEUED,
    )
    another_space = _space(factory, "Другое пространство")
    external = _document(factory, tmp_path, another_space.id, "чужой.txt")
    url = f"/api/spaces/{space.id}/relations"
    payload = {
        "source_document_id": str(supplement.id),
        "target_document_id": str(base.id),
        "relation_type": "supplements",
        "evidence": "ДС прямо указывает, что дополняет ФЗ-1.",
    }

    created = client.post(url, json=payload)

    assert created.status_code == 201, created.text
    relation = created.json()
    assert relation["status"] == "confirmed"
    assert relation["source_filename"] == "ДС-к-ФЗ-1.txt"
    assert relation["target_filename"] == "ФЗ-1.txt"
    assert client.get(url).json() == [relation]
    assert client.post(url, json=payload).status_code == 409
    self_link = client.post(url, json={**payload, "target_document_id": str(supplement.id)})
    cross_space = client.post(url, json={**payload, "target_document_id": str(external.id)})
    not_ready = client.post(url, json={**payload, "target_document_id": str(queued.id)})
    assert self_link.status_code == 422
    assert cross_space.status_code == 409
    assert not_ready.status_code == 409
    assert client.post(url, json={**payload, "relation_type": "looks_similar"}).status_code == 422
    assert client.get(f"/api/spaces/{uuid.uuid4()}/relations").status_code == 404

    assert client.delete(f"/api/relations/{relation['id']}").status_code == 204
    assert client.get(url).json() == []
    assert client.delete(f"/api/relations/{relation['id']}").status_code == 404


def test_deleting_document_removes_its_relations(relation_app: FastAPI, tmp_path: Path) -> None:
    client = TestClient(relation_app)
    factory = relation_app.state.session_factory
    space = _space(factory)
    base = _document(factory, tmp_path, space.id, "base.txt")
    supplement = _document(factory, tmp_path, space.id, "supplement.txt")
    url = f"/api/spaces/{space.id}/relations"
    created = client.post(
        url,
        json={
            "source_document_id": str(supplement.id),
            "target_document_id": str(base.id),
            "relation_type": "amends",
            "evidence": "Изменяет раздел 2.",
        },
    )
    assert created.status_code == 201

    assert client.delete(f"/api/documents/{base.id}").status_code == 204
    assert client.get(url).json() == []


class _Rows:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return self._rows


class _SequenceSession:
    def __init__(self, *results: list[Any]) -> None:
        self.results = list(results)

    def execute(self, _statement: object) -> _Rows:
        return _Rows(self.results.pop(0))


def _relation_row(
    source_id: uuid.UUID,
    target_id: uuid.UUID,
    target_filename: str,
    *,
    status: DocumentRelationStatus = DocumentRelationStatus.CONFIRMED,
) -> SimpleNamespace:
    return SimpleNamespace(
        relation_id=uuid.uuid4(),
        source_document_id=source_id,
        target_document_id=target_id,
        relation_type=DocumentRelationType.SUPPLEMENTS,
        relation_status=status,
        evidence="Подтверждённая ссылка",
        source_filename="base.txt",
        target_filename=target_filename,
    )


def _chunk_row(document_id: uuid.UUID, filename: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        document_id=document_id,
        filename=filename,
        location="раздел 1",
        content=f"Релевантное правило из {filename}",
        raw_score=0.71,
        storage_path=f"/data/{filename}",
    )


def test_graph_expansion_is_one_hop_bounded_and_ignores_suggestions() -> None:
    space_id, seed_id = uuid.uuid4(), uuid.uuid4()
    suggested_id, first_id, second_id, overflow_id = (
        uuid.uuid4(),
        uuid.uuid4(),
        uuid.uuid4(),
        uuid.uuid4(),
    )
    seed = RetrievedChunk(
        id=uuid.uuid4(),
        document_id=seed_id,
        filename="base.txt",
        location="раздел 1",
        content="Исходный результат hybrid search",
        score=0.9,
    )
    session = _SequenceSession(
        [
            _relation_row(
                seed_id,
                suggested_id,
                "suggested.txt",
                status=DocumentRelationStatus.SUGGESTED,
            ),
            _relation_row(seed_id, first_id, "first.txt"),
            _relation_row(seed_id, second_id, "second.txt"),
            _relation_row(seed_id, overflow_id, "overflow.txt"),
        ],
        [_chunk_row(first_id, "first.txt")],
        [_chunk_row(second_id, "second.txt")],
    )

    expanded = expand_related_context(
        session,  # type: ignore[arg-type]
        space_id=space_id,
        query_vector=[0.1] * 1024,
        retrieved=[seed],
        max_documents=2,
        chunks_per_document=1,
    )

    assert expanded[0] is seed
    assert [item.filename for item in expanded] == ["base.txt", "first.txt", "second.txt"]
    assert all(item.relation is not None for item in expanded[1:])
    assert expanded[1].relation is not None
    assert expanded[1].relation.relation_type == DocumentRelationType.SUPPLEMENTS
    assert not session.results


def test_source_payload_exposes_graph_provenance(
    relation_app: FastAPI, sqlite_factory: sessionmaker[Session]
) -> None:
    source_id, target_id = uuid.uuid4(), uuid.uuid4()
    relation = RelationProvenance(
        id=uuid.uuid4(),
        relation_type=DocumentRelationType.AMENDS,
        source_document_id=source_id,
        source_filename="ДС.txt",
        target_document_id=target_id,
        target_filename="ФЗ.txt",
        evidence="Изменяет пункт 4.",
    )
    related = RetrievedChunk(
        id=uuid.uuid4(),
        document_id=source_id,
        filename="ДС.txt",
        location="пункт 1",
        content="Новая редакция пункта 4.",
        score=0.7,
        relation=relation,
    )
    service = ChatService(
        relation_app.state.settings,
        sqlite_factory,
        relation_app.state.provider,
    )

    sources = service._build_sources([related], "Применяется новая редакция [1].")

    assert sources[0]["relation"] == {
        "id": str(relation.id),
        "type": "amends",
        "source_document_id": str(source_id),
        "source_filename": "ДС.txt",
        "target_document_id": str(target_id),
        "target_filename": "ФЗ.txt",
        "evidence": "Изменяет пункт 4.",
    }
