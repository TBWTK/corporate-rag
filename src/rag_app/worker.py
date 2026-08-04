from __future__ import annotations

import logging
import time

from rag_app.config import get_settings
from rag_app.db.session import create_database_engine, create_session_factory, initialize_database
from rag_app.providers.factory import create_provider
from rag_app.services.ingestion import IngestionWorker


def main() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logger = logging.getLogger("rag.worker")
    engine = create_database_engine(settings)
    initialize_database(engine)
    provider = create_provider(settings, engine=engine)
    worker = IngestionWorker(settings, create_session_factory(engine), provider)
    logger.info("Ingestion worker started")
    try:
        while True:
            processed = worker.process_next()
            if not processed:
                time.sleep(settings.worker_poll_seconds)
    except KeyboardInterrupt:
        logger.info("Ingestion worker stopped")
    finally:
        close = getattr(provider, "close", None)
        if callable(close):
            close()
        engine.dispose()


if __name__ == "__main__":
    main()
