from __future__ import annotations

import mimetypes
from pathlib import Path

from sqlalchemy import select

from rag_app.config import get_settings
from rag_app.db.models import KnowledgeSpace
from rag_app.db.session import create_database_engine, create_session_factory, initialize_database
from rag_app.services.ingestion import DuplicateDocumentError, UploadService


def collect_demo_documents(directory: Path) -> list[Path]:
    resolved = directory if directory.is_absolute() else Path.cwd() / directory
    if not resolved.is_dir():
        raise FileNotFoundError(f"Каталог демо-документов не найден: {resolved}")
    return sorted(path for path in resolved.iterdir() if path.is_file())


def main() -> None:
    settings = get_settings()
    engine = create_database_engine(settings)
    initialize_database(engine)
    factory = create_session_factory(engine)
    with factory() as session:
        space = session.scalar(select(KnowledgeSpace).where(KnowledgeSpace.name == "Демо: Acme"))
        if space is None:
            space = KnowledgeSpace(
                name="Демо: Acme",
                description="Связанные HR, командировочные и ИБ-документы вымышленной компании",
            )
            session.add(space)
            session.commit()
            session.refresh(space)

    upload = UploadService(settings, factory)
    added = 0
    for path in collect_demo_documents(settings.demo_documents_dir):
        try:
            upload.queue(
                space_id=space.id,
                filename=path.name,
                media_type=mimetypes.guess_type(path.name)[0],
                payload=path.read_bytes(),
            )
            added += 1
        except DuplicateDocumentError:
            pass
    print(f"Демо-пространство готово: добавлено документов — {added}")
    engine.dispose()


if __name__ == "__main__":
    main()
