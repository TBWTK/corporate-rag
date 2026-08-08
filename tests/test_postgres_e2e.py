from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from rag_app.config import Settings
from rag_app.db.models import Base, Chunk, Document
from rag_app.db.session import create_database_engine, create_session_factory, initialize_database
from rag_app.main import create_app
from rag_app.providers.fake import FakeProvider
from rag_app.retrieval.relations import expand_related_context
from rag_app.retrieval.search import RetrievedChunk
from rag_app.services.ingestion import IngestionWorker


@pytest.mark.integration
def test_postgres_upload_index_retrieve_and_chat(tmp_path: Path) -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not configured")
    settings = Settings(
        _env_file=None,
        llm_provider="fake",
        database_url=database_url,
        data_dir=tmp_path / "uploads",
        chunk_max_chars=600,
        chunk_overlap_chars=80,
    )
    engine = create_database_engine(settings)
    Base.metadata.drop_all(engine)
    initialize_database(engine)
    factory = create_session_factory(engine)

    with TestClient(create_app(settings)) as client:
        space = client.post(
            "/api/spaces",
            json={"name": "Acme", "description": "Связанные корпоративные политики"},
        ).json()
        files = []
        for path in sorted((Path("examples") / "acme-corp").iterdir()):
            files.append(("files", (path.name, path.read_bytes(), "application/octet-stream")))
        uploaded = client.post(f"/api/spaces/{space['id']}/documents", files=files)
        assert uploaded.status_code == 202
        assert len(uploaded.json()["documents"]) == 50

        worker = IngestionWorker(settings, factory, FakeProvider())
        while worker.process_next():
            pass
        documents = client.get(f"/api/spaces/{space['id']}/documents").json()
        assert {document["status"] for document in documents} == {"ready"}
        assert sum(document["chunk_count"] for document in documents) >= 20

        by_filename = {document["filename"]: document for document in documents}
        base = by_filename["work_format_policy.html"]
        supplement = by_filename["additional_agreement_finance_office.docx"]
        relation_response = client.post(
            f"/api/spaces/{space['id']}/relations",
            json={
                "source_document_id": supplement["id"],
                "target_document_id": base["id"],
                "relation_type": "supplements",
                "evidence": "Соглашение задаёт специальные условия финансового отдела.",
            },
        )
        assert relation_response.status_code == 201, relation_response.text
        assert client.get(f"/api/spaces/{space['id']}/relations").json()[0]["status"] == (
            "confirmed"
        )

        with factory() as session:
            base_document = session.get(Document, uuid.UUID(base["id"]))
            assert base_document is not None
            seed_chunk = session.scalar(
                select(Chunk)
                .where(Chunk.document_id == base_document.id)
                .order_by(Chunk.chunk_index)
            )
            assert seed_chunk is not None
            seed = RetrievedChunk(
                id=seed_chunk.id,
                document_id=base_document.id,
                filename=base_document.filename,
                location=seed_chunk.location,
                content=seed_chunk.content,
                score=0.9,
                storage_path=base_document.storage_path,
            )
            query_vector = FakeProvider().embed(["офисный график финансового отдела"])[0]
            expanded = expand_related_context(
                session,
                space_id=base_document.space_id,
                query_vector=query_vector,
                retrieved=[seed],
            )
        related = [item for item in expanded if item.relation is not None]
        assert related
        assert {item.filename for item in related} == {
            "additional_agreement_finance_office.docx"
        }

        answer = client.post(
            "/api/chat",
            json={
                "space_id": space["id"],
                "question": "Какой лимит гостиницы в Москве?",
            },
        )
        assert answer.status_code == 200, answer.text
        payload = answer.json()
        assert payload["sources"]
        assert any(
            source["filename"] in {"travel_policy.txt", "expense_limits.csv"}
            for source in payload["sources"]
        )
        assert "[1]" in payload["answer"]

    Base.metadata.drop_all(engine)
    engine.dispose()
