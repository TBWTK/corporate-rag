from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from rag_app.config import Settings
from rag_app.db.models import Chunk, Document, DocumentStatus, KnowledgeSpace
from rag_app.providers.fake import FakeProvider
from rag_app.services.ingestion import (
    DuplicateDocumentError,
    IngestionWorker,
    SpaceNotFoundError,
    UploadService,
    UploadValidationError,
)


def make_settings(tmp_path: Path, **overrides: object) -> Settings:
    return Settings(
        _env_file=None,
        llm_provider="fake",
        data_dir=tmp_path / "uploads",
        **overrides,
    )


def add_space(factory: sessionmaker[Session]) -> KnowledgeSpace:
    with factory() as session:
        space = KnowledgeSpace(name="HR")
        session.add(space)
        session.commit()
        session.refresh(space)
        return space


def test_upload_queue_deduplicates_and_validates(
    tmp_path: Path, sqlite_factory: sessionmaker[Session]
) -> None:
    settings = make_settings(tmp_path, max_upload_mb=1)
    service = UploadService(settings, sqlite_factory)
    space = add_space(sqlite_factory)

    document = service.queue(
        space_id=space.id,
        filename="../policy.txt",
        media_type="text/plain",
        payload="Политика отпусков".encode(),
    )

    assert document.filename == "policy.txt"
    assert document.status == DocumentStatus.QUEUED
    assert Path(document.storage_path).read_text() == "Политика отпусков"
    with pytest.raises(DuplicateDocumentError) as duplicate:
        service.queue(
            space_id=space.id,
            filename="copy.txt",
            media_type="text/plain",
            payload="Политика отпусков".encode(),
        )
    assert duplicate.value.document.id == document.id

    with pytest.raises(UploadValidationError, match="не поддерживается"):
        service.queue(space_id=space.id, filename="bad.zip", media_type=None, payload=b"x")
    with pytest.raises(UploadValidationError, match="пустой"):
        service.queue(space_id=space.id, filename="empty.txt", media_type=None, payload=b"")
    with pytest.raises(UploadValidationError, match="больше"):
        service.queue(
            space_id=space.id,
            filename="huge.txt",
            media_type=None,
            payload=b"x" * (settings.max_upload_bytes + 1),
        )
    with pytest.raises(SpaceNotFoundError):
        service.queue(
            space_id=uuid.uuid4(), filename="orphan.txt", media_type=None, payload=b"text"
        )


def test_worker_processes_document_and_marks_invalid_text_error(
    tmp_path: Path, sqlite_factory: sessionmaker[Session]
) -> None:
    settings = make_settings(tmp_path, chunk_max_chars=128, chunk_overlap_chars=20)
    service = UploadService(settings, sqlite_factory)
    space = add_space(sqlite_factory)
    ready = service.queue(
        space_id=space.id,
        filename="policy.txt",
        media_type="text/plain",
        payload=("Отпуск согласуется за 14 дней. " * 12).encode(),
    )
    broken = service.queue(
        space_id=space.id,
        filename="broken.txt",
        media_type="text/plain",
        payload=b"  \n",
    )
    worker = IngestionWorker(settings, sqlite_factory, FakeProvider())

    assert worker.process_next() is True
    assert worker.process_next() is True
    assert worker.process_next() is False

    with sqlite_factory() as session:
        processed = session.get(Document, ready.id)
        failed = session.get(Document, broken.id)
        assert processed is not None and processed.status == DocumentStatus.READY
        assert processed.chunk_count >= 2
        assert session.scalar(select(Chunk).where(Chunk.document_id == ready.id)) is not None
        assert failed is not None and failed.status == DocumentStatus.ERROR
        assert failed.error


def test_worker_rejects_wrong_embedding_dimension(
    tmp_path: Path, sqlite_factory: sessionmaker[Session]
) -> None:
    settings = make_settings(tmp_path)
    space = add_space(sqlite_factory)
    document = UploadService(settings, sqlite_factory).queue(
        space_id=space.id, filename="policy.md", media_type="text/markdown", payload=b"content"
    )
    IngestionWorker(settings, sqlite_factory, FakeProvider(dimension=8)).process_next()

    with sqlite_factory() as session:
        failed = session.get(Document, document.id)
        assert failed is not None and failed.status == DocumentStatus.ERROR
        assert "1024" in (failed.error or "")
