from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.orm import Session, sessionmaker

from rag_app.config import Settings
from rag_app.db.models import Chunk, Document, DocumentStatus, KnowledgeSpace
from rag_app.domain.chunking import TextChunk, chunk_text
from rag_app.ingestion.extractors import (
    SUPPORTED_EXTENSIONS,
    ExtractedDocument,
    ExtractedUnit,
    extract_document,
)
from rag_app.ingestion.vision import VISION_SYSTEM_PROMPT, build_page_prompt, parse_visual_page
from rag_app.ingestion.visual import (
    VISUAL_EXTENSIONS,
    document_has_visuals,
    page_number_from_location,
    render_document_pages,
)
from rag_app.providers.base import ModelProvider, ProviderError, VisionModelProvider


class SpaceNotFoundError(LookupError):
    pass


class DuplicateDocumentError(ValueError):
    def __init__(self, document: Document) -> None:
        super().__init__("Этот документ уже загружен в пространство")
        self.document = document


class UploadValidationError(ValueError):
    pass


def _safe_filename(filename: str) -> str:
    clean = Path(filename.replace("\\", "/")).name.strip().replace("\x00", "")
    if not clean or clean in {".", ".."}:
        raise UploadValidationError("Некорректное имя файла")
    return clean[:255]


class UploadService:
    def __init__(self, settings: Settings, session_factory: sessionmaker[Session]) -> None:
        self.settings = settings
        self.session_factory = session_factory

    def queue(
        self,
        *,
        space_id: uuid.UUID,
        filename: str,
        media_type: str | None,
        payload: bytes,
    ) -> Document:
        safe_name = _safe_filename(filename)
        suffix = Path(safe_name).suffix.casefold()
        if suffix not in SUPPORTED_EXTENSIONS:
            allowed = ", ".join(sorted(SUPPORTED_EXTENSIONS))
            raise UploadValidationError(
                f"Формат {suffix or '<без расширения>'} не поддерживается: {allowed}"
            )
        if not payload:
            raise UploadValidationError("Нельзя загрузить пустой файл")
        if len(payload) > self.settings.max_upload_bytes:
            raise UploadValidationError(f"Файл больше допустимых {self.settings.max_upload_mb} МБ")

        digest = hashlib.sha256(payload).hexdigest()
        with self.session_factory() as session:
            if session.get(KnowledgeSpace, space_id) is None:
                raise SpaceNotFoundError("Пространство знаний не найдено")
            duplicate = session.scalar(
                select(Document).where(
                    Document.space_id == space_id,
                    Document.sha256 == digest,
                )
            )
            if duplicate is not None:
                raise DuplicateDocumentError(duplicate)

            document_id = uuid.uuid4()
            directory = self.settings.data_dir / str(space_id) / str(document_id)
            directory.mkdir(parents=True, exist_ok=True)
            target = directory / safe_name
            target.write_bytes(payload)
            document = Document(
                id=document_id,
                space_id=space_id,
                filename=safe_name,
                media_type=media_type or "application/octet-stream",
                storage_path=str(target),
                sha256=digest,
                status=DocumentStatus.QUEUED,
            )
            session.add(document)
            try:
                session.commit()
            except Exception:
                target.unlink(missing_ok=True)
                raise
            session.refresh(document)
            return document


class IngestionWorker:
    def __init__(
        self,
        settings: Settings,
        session_factory: sessionmaker[Session],
        provider: ModelProvider,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.provider = provider

    def claim_next(self) -> uuid.UUID | None:
        cutoff = datetime.now(UTC) - timedelta(minutes=self.settings.processing_timeout_minutes)
        with self.session_factory() as session, session.begin():
            document = session.scalar(
                select(Document)
                .where(
                    or_(
                        Document.status == DocumentStatus.QUEUED,
                        and_(
                            Document.status == DocumentStatus.PROCESSING,
                            Document.processing_started_at < cutoff,
                        ),
                    )
                )
                .order_by(Document.created_at)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if document is None:
                return None
            document.status = DocumentStatus.PROCESSING
            document.error = None
            document.processing_started_at = datetime.now(UTC)
            return document.id

    def process_next(self) -> bool:
        document_id = self.claim_next()
        if document_id is None:
            return False
        self.process(document_id)
        return True

    def process(self, document_id: uuid.UUID) -> None:
        try:
            with self.session_factory() as session:
                document = session.get(Document, document_id)
                if document is None:
                    return
                path = Path(document.storage_path)
                space_id = document.space_id

            extracted = extract_document(path)
            visual_units = self._extract_visual_units(path, extracted)
            chunks: list[TextChunk] = []
            for unit in (*extracted.units, *visual_units):
                for chunk in chunk_text(
                    unit.text,
                    max_chars=self.settings.chunk_max_chars,
                    overlap_chars=self.settings.chunk_overlap_chars,
                    location=unit.location,
                ):
                    chunks.append(
                        TextChunk(index=len(chunks), text=chunk.text, location=chunk.location)
                    )
            if not chunks:
                raise ValueError("После разбиения документ не содержит текста")

            vectors: list[list[float]] = []
            batch_size = self.settings.embedding_batch_size
            for offset in range(0, len(chunks), batch_size):
                batch = chunks[offset : offset + batch_size]
                vectors.extend(self.provider.embed([chunk.text for chunk in batch]))
            if len(vectors) != len(chunks):
                raise ProviderError("Провайдер вернул неполный набор эмбеддингов")
            if any(len(vector) != self.settings.embedding_dimension for vector in vectors):
                raise ProviderError(
                    f"Ожидалась размерность эмбеддинга {self.settings.embedding_dimension}"
                )

            with self.session_factory() as session, session.begin():
                document = session.get(Document, document_id, with_for_update=True)
                if document is None:
                    return
                session.execute(delete(Chunk).where(Chunk.document_id == document_id))
                session.add_all(
                    [
                        Chunk(
                            document_id=document_id,
                            space_id=space_id,
                            chunk_index=chunk.index,
                            content=chunk.text,
                            location=chunk.location,
                            embedding=vector,
                        )
                        for chunk, vector in zip(chunks, vectors, strict=True)
                    ]
                )
                document.status = DocumentStatus.READY
                document.error = None
                document.chunk_count = len(chunks)
                document.processing_started_at = None
        except Exception as error:
            self._mark_error(document_id, error)

    def _extract_visual_units(
        self, path: Path, extracted: ExtractedDocument
    ) -> tuple[ExtractedUnit, ...]:
        if (
            not self.settings.vision_ingestion_enabled
            or path.suffix.casefold() not in VISUAL_EXTENSIONS
            or not isinstance(self.provider, VisionModelProvider)
            or not document_has_visuals(path)
        ):
            return ()

        pages = render_document_pages(
            path,
            path.parent / "pages",
            dpi=self.settings.visual_page_dpi,
            timeout_seconds=self.settings.visual_render_timeout_seconds,
        )
        if len(pages) > self.settings.visual_max_pages:
            raise ValueError(
                f"В документе {len(pages)} страниц; лимит visual ingestion — "
                f"{self.settings.visual_max_pages}"
            )

        native_by_page: dict[int, str] = {}
        for unit in extracted.units:
            page_number = page_number_from_location(unit.location)
            if page_number is not None:
                native_by_page[page_number] = unit.text

        vision_provider = cast(VisionModelProvider, self.provider)
        units: list[ExtractedUnit] = []
        for page in pages:
            task = build_page_prompt(
                extracted.title,
                page.number,
                native_by_page.get(page.number, ""),
            )
            completion = vision_provider.analyze_image(
                page.path,
                prompt=f"{VISION_SYSTEM_PROMPT}\n\n{task}",
            )
            page_units = parse_visual_page(completion.text, page_number=page.number)
            if not page_units:
                raise ProviderError(f"GigaChat не извлёк содержимое страницы {page.number}")
            units.extend(page_units)
        return tuple(units)

    def _mark_error(self, document_id: uuid.UUID, error: Exception) -> None:
        if isinstance(error, (ValueError, ProviderError)):
            message = str(error)
        else:
            message = f"Внутренняя ошибка обработки ({type(error).__name__})"
        with self.session_factory() as session, session.begin():
            document = session.get(Document, document_id, with_for_update=True)
            if document is not None:
                document.status = DocumentStatus.ERROR
                document.error = message[:500]
                document.processing_started_at = None
