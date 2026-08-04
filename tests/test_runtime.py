from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from rag_app.config import Settings
from rag_app.db.models import KnowledgeSpace
from rag_app.db.session import (
    create_database_engine,
    create_session_factory,
    database_is_ready,
    session_scope,
)
from rag_app.main import create_app
from rag_app.providers.fake import FakeProvider
from rag_app.providers.serialized import PostgresSerializedProvider


def test_database_factory_readiness_and_session_scope() -> None:
    settings = Settings(
        _env_file=None,
        llm_provider="fake",
        database_url="sqlite+pysqlite:///:memory:",
    )
    engine = create_database_engine(settings)
    factory = create_session_factory(engine)

    assert database_is_ready(engine) is True
    with session_scope(factory) as session:
        session.execute(text("CREATE TABLE probe (value INTEGER)"))
        session.execute(text("INSERT INTO probe VALUES (1)"))
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM probe")) == 1

    with pytest.raises(RuntimeError), session_scope(factory) as session:
        session.add(KnowledgeSpace(name="will rollback"))
        raise RuntimeError("rollback")
    engine.dispose()


def test_database_readiness_handles_connection_failure() -> None:
    engine = Mock()
    engine.connect.side_effect = RuntimeError("offline")
    assert database_is_ready(engine) is False


class FakeConnection:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def __enter__(self) -> FakeConnection:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, statement: Any, _params: dict[str, int]) -> None:
        self.statements.append(str(statement))


class FakeEngine:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    def connect(self) -> FakeConnection:
        return self.connection


def test_serialized_provider_locks_embed_generate_and_closes() -> None:
    connection = FakeConnection()
    inner = FakeProvider(dimension=8)
    inner.close = Mock()  # type: ignore[attr-defined]
    provider = PostgresSerializedProvider(inner, FakeEngine(connection))  # type: ignore[arg-type]

    assert len(provider.embed(["контекст"])[0]) == 8
    assert provider.generate([{"role": "user", "content": "вопрос"}]).text
    provider.close()

    assert sum("pg_advisory_lock" in statement for statement in connection.statements) == 2
    assert sum("pg_advisory_unlock" in statement for statement in connection.statements) == 2
    inner.close.assert_called_once()  # type: ignore[attr-defined]


def test_create_app_serves_ui_and_openapi_without_starting_runtime(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        llm_provider="fake",
        data_dir=tmp_path / "uploads",
        database_url="sqlite+pysqlite:///:memory:",
    )
    client = TestClient(create_app(settings))

    index = client.get("/")
    assert index.status_code == 200
    assert "Контекст" in index.text
    assert client.get("/api/openapi.json").status_code == 200
