from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from rag_app.api.routes import router
from rag_app.config import Settings
from rag_app.providers.base import Completion, ProviderError
from rag_app.providers.fake import FakeProvider
from rag_app.retrieval.search import RetrievedChunk
from rag_app.services.ingestion import IngestionWorker


@pytest.fixture
def api_app(tmp_path: Path, sqlite_factory: sessionmaker[Session]) -> FastAPI:
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


def create_space(client: TestClient, name: str = "HR") -> dict[str, object]:
    response = client.post("/api/spaces", json={"name": name, "description": "Политики"})
    assert response.status_code == 201
    return response.json()


def test_health_config_and_space_crud(api_app: FastAPI) -> None:
    client = TestClient(api_app)

    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    config = client.get("/api/config").json()
    assert ".pdf" in config["supported_extensions"]
    assert "api_key" not in config

    space = create_space(client)
    assert client.get("/api/spaces").json()[0]["document_count"] == 0
    assert client.post("/api/spaces", json={"name": "   "}).status_code == 422
    assert client.get(f"/api/spaces/{uuid.uuid4()}/documents").status_code == 404
    assert space["name"] == "HR"


def test_upload_duplicate_retry_and_delete(api_app: FastAPI) -> None:
    client = TestClient(api_app)
    space = create_space(client)
    url = f"/api/spaces/{space['id']}/documents"

    uploaded = client.post(url, files=[("files", ("policy.txt", b"14 days", "text/plain"))])
    assert uploaded.status_code == 202
    document = uploaded.json()["documents"][0]
    duplicate = client.post(url, files=[("files", ("copy.txt", b"14 days", "text/plain"))])
    assert duplicate.status_code == 202
    assert duplicate.json()["duplicates"][0]["id"] == document["id"]
    assert len(client.get(url).json()) == 1

    retried = client.post(f"/api/documents/{document['id']}/retry")
    assert retried.status_code == 200
    assert retried.json()["status"] == "queued"
    assert client.post(f"/api/documents/{uuid.uuid4()}/retry").status_code == 404
    assert client.delete(f"/api/documents/{document['id']}").status_code == 204
    assert client.delete(f"/api/documents/{document['id']}").status_code == 404


def test_upload_validation_errors(api_app: FastAPI) -> None:
    client = TestClient(api_app)
    space = create_space(client)
    url = f"/api/spaces/{space['id']}/documents"

    assert client.post(url, files=[("files", ("bad.zip", b"x"))]).status_code == 422
    assert client.post(url, files=[("files", ("empty.txt", b""))]).status_code == 422
    assert (
        client.post(
            f"/api/spaces/{uuid.uuid4()}/documents",
            files=[("files", ("ok.txt", b"text"))],
        ).status_code
        == 404
    )


def test_chat_persists_messages_and_sources(
    api_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = TestClient(api_app)
    space = create_space(client)
    upload_url = f"/api/spaces/{space['id']}/documents"
    document = client.post(
        upload_url,
        files=[("files", ("policy.txt", b"Hotel limit is 10000 rubles", "text/plain"))],
    ).json()["documents"][0]
    IngestionWorker(
        api_app.state.settings,
        api_app.state.session_factory,
        api_app.state.provider,
    ).process_next()

    def fake_search(*_args: object, **_kwargs: object) -> list[RetrievedChunk]:
        return [
            RetrievedChunk(
                id=uuid.uuid4(),
                document_id=uuid.UUID(document["id"]),
                filename="policy.txt",
                location="текст",
                content="Hotel limit is 10000 rubles",
                score=0.03,
            )
        ]

    monkeypatch.setattr("rag_app.services.chat.hybrid_search", fake_search)
    response = client.post(
        "/api/chat",
        json={"space_id": space["id"], "question": "What is the hotel limit?"},
    )
    assert response.status_code == 200
    answer = response.json()
    assert answer["sources"][0]["filename"] == "policy.txt"
    assert "[1]" in answer["answer"]

    follow_up = client.post(
        "/api/chat",
        json={
            "space_id": space["id"],
            "question": "Repeat",
            "conversation_id": answer["conversation_id"],
        },
    )
    assert follow_up.status_code == 200
    messages = client.get(f"/api/conversations/{answer['conversation_id']}/messages")
    assert [message["role"] for message in messages.json()] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]
    assert client.get(f"/api/conversations/{uuid.uuid4()}/messages").status_code == 404


def test_chat_errors_are_mapped(api_app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    client = TestClient(api_app)
    empty_space = create_space(client, "Empty")
    assert (
        client.post(
            "/api/chat", json={"space_id": empty_space["id"], "question": "Question"}
        ).status_code
        == 409
    )

    ready_space = create_space(client, "Ready")
    client.post(
        f"/api/spaces/{ready_space['id']}/documents",
        files=[("files", ("ready.txt", b"content", "text/plain"))],
    )
    IngestionWorker(
        api_app.state.settings,
        api_app.state.session_factory,
        api_app.state.provider,
    ).process_next()
    monkeypatch.setattr("rag_app.services.chat.hybrid_search", lambda *_args, **_kwargs: [])

    class BrokenProvider:
        def embed(self, _texts: list[str]) -> list[list[float]]:
            raise ProviderError("provider unavailable")

        def generate(self, _messages: list[dict[str, str]]) -> Completion:
            raise AssertionError("not reached")

    api_app.state.provider = BrokenProvider()
    failed = client.post("/api/chat", json={"space_id": ready_space["id"], "question": "Question"})
    assert failed.status_code == 502
    assert failed.json()["detail"] == "provider unavailable"

    api_app.state.provider = None
    assert client.get("/api/health").json()["status"] == "degraded"
