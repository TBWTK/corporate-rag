from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from rag_app.api.routes import router
from rag_app.config import Settings
from rag_app.db.models import Document
from rag_app.providers.base import Completion, ProviderError
from rag_app.providers.fake import FakeProvider
from rag_app.retrieval.search import RetrievedChunk
from rag_app.services.chat import _cited_source_groups
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
    with api_app.state.session_factory() as session:
        stored = session.get(Document, uuid.UUID(document["id"]))
        assert stored is not None
        storage_directory = Path(stored.storage_path).parent
    pages = storage_directory / "pages"
    pages.mkdir()
    (pages / "page-1.png").write_bytes(b"page")
    assert client.delete(f"/api/documents/{document['id']}").status_code == 204
    assert not storage_directory.exists()
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
    with api_app.state.session_factory() as session:
        stored = session.get(Document, uuid.UUID(document["id"]))
        assert stored is not None
        storage_path = Path(stored.storage_path)
    page_dir = storage_path.parent / "pages"
    page_dir.mkdir()
    page_payload = b"fake-png-for-api"
    (page_dir / "page-1.png").write_bytes(page_payload)

    def fake_search(*_args: object, **_kwargs: object) -> list[RetrievedChunk]:
        return [
            RetrievedChunk(
                id=uuid.uuid4(),
                document_id=uuid.UUID(document["id"]),
                filename="policy.txt",
                location="стр. 1 · шаг 1",
                content="Hotel limit is 10000 rubles",
                score=0.03,
                storage_path=str(storage_path),
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
    assert answer["sources"][0]["image_url"] == (f"/api/documents/{document['id']}/pages/1")
    page_response = client.get(answer["sources"][0]["image_url"])
    assert page_response.status_code == 200
    assert page_response.content == page_payload
    assert client.get(f"/api/documents/{document['id']}/pages/0").status_code == 404
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


def test_chat_clarification_and_follow_up_use_shared_conversation(
    api_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = TestClient(api_app)
    space = create_space(client, "Дополнительные соглашения")
    document = client.post(
        f"/api/spaces/{space['id']}/documents",
        files=[("files", ("remote-sales.txt", b"Sales remote rule", "text/plain"))],
    ).json()["documents"][0]

    class ClarifyingProvider(FakeProvider):
        def __init__(self) -> None:
            super().__init__()
            self.embedding_inputs: list[str] = []
            self.generation_count = 0

        def embed(self, texts: list[str]) -> list[list[float]]:
            self.embedding_inputs.extend(texts)
            return super().embed(texts)

        def generate(self, _messages: list[dict[str, str]]) -> Completion:
            self.generation_count += 1
            if self.generation_count == 1:
                payload = {
                    "response_type": "clarification",
                    "question": "Для какого подразделения проверить удалённый режим?",
                    "options": ["Отдел продаж", "Разработка"],
                }
            else:
                payload = {
                    "response_type": "answer",
                    "answer": "Для отдела продаж разрешено три удалённых дня [1].",
                }
            return Completion(text=json.dumps(payload, ensure_ascii=False), model="scripted")

    provider = ClarifyingProvider()
    api_app.state.provider = provider
    IngestionWorker(
        api_app.state.settings,
        api_app.state.session_factory,
        provider,
    ).process_next()

    def fake_search(*_args: object, **_kwargs: object) -> list[RetrievedChunk]:
        return [
            RetrievedChunk(
                id=uuid.uuid4(),
                document_id=uuid.UUID(document["id"]),
                filename="remote-sales.txt",
                location="раздел 2",
                content="Для отдела продаж разрешено три удалённых дня.",
                score=0.04,
            )
        ]

    monkeypatch.setattr("rag_app.services.chat.hybrid_search", fake_search)
    first = client.post(
        "/api/chat",
        json={"space_id": space["id"], "question": "Сколько дней можно работать удалённо?"},
    )

    assert first.status_code == 200
    clarification = first.json()
    assert clarification["response_type"] == "clarification"
    assert clarification["clarification_options"] == ["Отдел продаж", "Разработка"]

    second = client.post(
        "/api/chat",
        json={
            "space_id": space["id"],
            "question": "Отдел продаж",
            "conversation_id": clarification["conversation_id"],
        },
    )

    assert second.status_code == 200
    assert second.json()["response_type"] == "answer"
    assert "три" in second.json()["answer"]
    retrieval_query = provider.embedding_inputs[-1]
    assert "Сколько дней можно работать удалённо?" in retrieval_query
    assert "Отдел продаж" in retrieval_query


def test_visual_chat_clarifies_scenario_before_generation(
    api_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = TestClient(api_app)
    space = create_space(client, "Рабочие инструкции")
    uploaded = client.post(
        f"/api/spaces/{space['id']}/documents",
        files=[
            ("files", ("ios.txt", b"iOS mail", "text/plain")),
            ("files", ("outlook.txt", b"Outlook mail", "text/plain")),
        ],
    ).json()["documents"]

    class TrackingProvider(FakeProvider):
        def __init__(self) -> None:
            super().__init__()
            self.generation_count = 0

        def generate(self, messages: list[dict[str, str]]) -> Completion:
            self.generation_count += 1
            return Completion(
                text=json.dumps(
                    {
                        "response_type": "answer",
                        "answer": "Откройте Outlook и добавьте учётную запись [1].",
                    },
                    ensure_ascii=False,
                ),
                model="scripted",
            )

    provider = TrackingProvider()
    api_app.state.provider = provider
    worker = IngestionWorker(api_app.state.settings, api_app.state.session_factory, provider)
    while worker.process_next():
        pass

    ios_id = uuid.UUID(uploaded[0]["id"])
    outlook_id = uuid.UUID(uploaded[1]["id"])

    def fake_search(*_args: object, **_kwargs: object) -> list[RetrievedChunk]:
        return [
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

    monkeypatch.setattr("rag_app.services.chat.hybrid_search", fake_search)
    clarification_response = client.post(
        "/api/chat",
        json={
            "space_id": space["id"],
            "question": "Настройка почты на мобильных устройствах",
        },
    )

    assert clarification_response.status_code == 200
    clarification = clarification_response.json()
    assert clarification["response_type"] == "clarification"
    assert clarification["clarification_options"] == [
        "Стандартная почта iOS",
        "Настройка почты мобильные устройства Outlook",
    ]
    assert clarification["sources"] == []
    assert provider.generation_count == 0

    answer_response = client.post(
        "/api/chat",
        json={
            "space_id": space["id"],
            "question": "Настройка почты мобильные устройства Outlook",
            "conversation_id": clarification["conversation_id"],
        },
    )

    assert answer_response.status_code == 200
    answer = answer_response.json()
    assert answer["response_type"] == "answer"
    assert [source["filename"] for source in answer["sources"]] == [
        "Настройка почты мобильные устройства Outlook.pdf"
    ]
    assert provider.generation_count == 1


def test_cited_source_groups_merge_steps_on_the_same_page() -> None:
    document_id = uuid.uuid4()
    page_one_step_one = RetrievedChunk(
        id=uuid.uuid4(),
        document_id=document_id,
        filename="guide.pdf",
        location="стр. 1 · шаг 1",
        content="Шаг 1: Откройте настройки",
        score=0.05,
    )
    page_one_step_two = RetrievedChunk(
        id=uuid.uuid4(),
        document_id=document_id,
        filename="guide.pdf",
        location="стр. 1 · шаг 2",
        content="Шаг 2: Выберите почту",
        score=0.05,
    )
    page_two = RetrievedChunk(
        id=uuid.uuid4(),
        document_id=document_id,
        filename="guide.pdf",
        location="стр. 2 · шаг 3",
        content="Шаг 3: Введите адрес",
        score=0.05,
    )
    unused = RetrievedChunk(
        id=uuid.uuid4(),
        document_id=document_id,
        filename="guide.pdf",
        location="стр. 3 · шаг 4",
        content="Шаг 4: Не процитирован",
        score=0.05,
    )

    groups = _cited_source_groups(
        "Откройте настройки [2], затем введите адрес [3]. Также см. [1].",
        [page_one_step_one, page_one_step_two, page_two, unused],
    )

    assert len(groups) == 2
    assert groups[0].citation_numbers == (1, 2)
    assert groups[0].items == (page_one_step_one, page_one_step_two)
    assert groups[1].citation_numbers == (3,)
    assert groups[1].items == (page_two,)


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
