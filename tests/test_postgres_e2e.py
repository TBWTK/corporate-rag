from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from rag_app.config import Settings
from rag_app.db.models import Base
from rag_app.db.session import create_database_engine, create_session_factory, initialize_database
from rag_app.main import create_app
from rag_app.providers.fake import FakeProvider
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
        assert len(uploaded.json()["documents"]) == 20

        worker = IngestionWorker(settings, factory, FakeProvider())
        while worker.process_next():
            pass
        documents = client.get(f"/api/spaces/{space['id']}/documents").json()
        assert {document["status"] for document in documents} == {"ready"}
        assert sum(document["chunk_count"] for document in documents) >= 20

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
