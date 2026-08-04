---
title: Текущее состояние
type: state
status: complete
updated: 2026-08-04
---

# Текущее состояние

## Active objective

Завершено: локальный Docker-продукт «Контекст» проверен на загрузке связанных документов, индексации и чате со ссылками на источники.

## Acceptance criteria

- [x] Git-репозиторий и структура проекта инициализированы.
- [x] Test-first контракты покрывают chunking, parsing, RRF и grounded prompt.
- [x] `docker compose up --build` поднимает здоровые `db`, `api`, `worker`.
- [x] TXT, MD, CSV, PDF, DOCX, XLSX, PPTX и HTML извлекаются и индексируются.
- [x] Связанные файлы изолированы пространством знаний и находятся гибридным поиском.
- [x] Чат возвращает ответ и нумерованные источники; история диалога сохраняется.
- [x] Демо-набор Acme проходит capability eval без внешних токенов.
- [x] Live smoke GigaChat подтверждает OAuth, embedding и generation без раскрытия ключей.
- [x] Ruff, mypy, pytest/coverage и визуальный QA проходят.
- [x] Русская документация содержит аудит, пользовательский и системный Mermaid-flow.

## Current verified state

- Git: ветка `main`; продукт и Docker-приёмка зафиксированы Conventional Commits.
- Красная TDD-база: четыре import failure до реализации домена.
- Зелёная TDD-база: `10 passed` для chunking, text extractors, RRF и prompting 04.08.2026.
- Docker build выполнен; `db`, `api`, `worker` имеют статус `healthy`.
- `make demo`: 4 документа добавлены, повторный запуск добавил 0; все документы `ready`.
- Docker HTTP e2e: health → spaces → documents → chat; источники включают политику и таблицу лимитов.
- Docker live e2e: 4 документа переиндексированы `Embeddings-2`, ответ получен от `GigaChat-2-Pro:2.0.30.01` с цитатами `[1][2]`.
- `37 passed, 2 skipped`, branch coverage 83,98%; Ruff и strict mypy без ошибок внутри образа.
- PostgreSQL 17 + pgvector 0.8 e2e: upload 4 файлов → ready → hybrid chat, `1 passed`.
- Live GigaChat: официальный CA, OAuth, Embeddings-2/1024 и GigaChat-2-Pro, `1 passed`.
- Browser QA: desktop и 390×844, без horizontal overflow и console warnings/errors.
- `docker compose config` валиден; Docker Compose build и runtime e2e пройдены.

## Changed areas

- `src/rag_app/`: API, ingestion worker, providers, retrieval, web UI.
- `tests/`: unit-контракты.
- `Dockerfile`, `docker-compose.yml`, `Makefile`, `pyproject.toml`.
- `examples/acme-corp/` и русская документация.

## Decisions made

- PostgreSQL/pgvector и гибридный RRF вместо in-memory vector store.
- `Embeddings-2`/1024 как фиксированная индексная схема; `GigaChat-2-Pro` для ответа.
- PostgreSQL advisory lock сериализует GigaChat между API и worker.
- Compose использует `RAG_LLM_PROVIDER`, чтобы legacy-переменная `LLM_PROVIDER` в существующем `.env` не отключала GigaChat.

## Next exact step

Нет: текущий этап завершён. Следующий продуктовый этап определяется отдельной задачей.

## Blockers

- Нет. Локальное зависание Docker credential helper обойдено одноразовым анонимным config без изменения глобальных настроек.

## Non-goals

- OCR для изображений и сканированных PDF.
- SSO, RBAC, ACL на уровне отдельных документов.
- Высокодоступный кластер и горизонтальное масштабирование worker.

## Verification

```bash
python3 -m pytest tests/test_chunking.py tests/test_extractors.py tests/test_fusion.py tests/test_prompting.py
# 10 passed in 0.01s — 2026-08-04

.venv/bin/pytest --cov=rag_app --cov-report=term-missing
# 37 passed, 2 skipped; 83.98% — 2026-08-04

TEST_DATABASE_URL=postgresql+psycopg://... .venv/bin/pytest -m integration tests/test_postgres_e2e.py
# 1 passed — PostgreSQL 17 + pgvector 0.8

RUN_LIVE_GIGACHAT=1 .venv/bin/pytest -m live tests/test_gigachat_live.py
# 1 passed — Embeddings-2 + GigaChat-2-Pro

docker compose up --build -d
make demo
make test
make lint
docker compose ps
# db, api, worker healthy; Docker e2e passed — 2026-08-04
```
