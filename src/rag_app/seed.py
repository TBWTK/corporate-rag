from __future__ import annotations

import mimetypes
from pathlib import Path

from sqlalchemy import select

from rag_app.config import get_settings
from rag_app.db.models import KnowledgeSpace
from rag_app.db.session import create_database_engine, create_session_factory, initialize_database
from rag_app.services.ingestion import DuplicateDocumentError, UploadService


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
    examples = Path(__file__).resolve().parents[2] / "examples" / "acme-corp"
    added = 0
    for path in sorted(examples.iterdir()):
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
