---
title: Текущее состояние
type: state
status: active
updated: 2026-08-04
---

# Текущее состояние

## Active objective

Довести локальный Docker-продукт «Контекст» до проверенного сценария: загрузить разноформатные связанные документы, дождаться индексации и получить ответ GigaChat со ссылками на источники.

## Acceptance criteria

- [x] Git-репозиторий и структура проекта инициализированы.
- [x] Test-first контракты покрывают chunking, parsing, RRF и grounded prompt.
- [ ] `docker compose up --build` поднимает здоровые `db`, `api`, `worker`.
- [x] TXT, MD, CSV, PDF, DOCX, XLSX, PPTX и HTML извлекаются и индексируются.
- [x] Связанные файлы изолированы пространством знаний и находятся гибридным поиском.
- [x] Чат возвращает ответ и нумерованные источники; история диалога сохраняется.
- [x] Демо-набор Acme проходит capability eval без внешних токенов.
- [x] Live smoke GigaChat подтверждает OAuth, embedding и generation без раскрытия ключей.
- [x] Ruff, mypy, pytest/coverage и визуальный QA проходят.
- [x] Русская документация содержит аудит, пользовательский и системный Mermaid-flow.

## Current verified state

- Git: ветка `main`, исходный commit `75af2ee chore: initialize repository`.
- Красная TDD-база: четыре import failure до реализации домена.
- Зелёная TDD-база: `10 passed` для chunking, text extractors, RRF и prompting 04.08.2026.
- `36 passed, 2 skipped`, branch coverage 82,99%; Ruff и strict mypy без ошибок.
- PostgreSQL 17 + pgvector 0.8 e2e: upload 4 файлов → ready → hybrid chat, `1 passed`.
- Live GigaChat: официальный CA, OAuth, Embeddings-2/1024 и GigaChat-2-Pro, `1 passed`.
- Browser QA: desktop и 390×844, без horizontal overflow и console warnings/errors.
- `docker compose config` валиден; build не выполнен из-за недоступности registry через Docker Desktop proxy.

## Changed areas

- `src/rag_app/`: API, ingestion worker, providers, retrieval, web UI.
- `tests/`: unit-контракты.
- `Dockerfile`, `docker-compose.yml`, `Makefile`, `pyproject.toml`.
- `examples/acme-corp/` и русская документация.

## Decisions made

- PostgreSQL/pgvector и гибридный RRF вместо in-memory vector store.
- `Embeddings-2`/1024 как фиксированная индексная схема; `GigaChat-2-Pro` для ответа.
- PostgreSQL advisory lock сериализует GigaChat между API и worker.

## Next exact step

Когда Docker registry станет доступен, выполнить `docker compose up --build -d`, `make demo` и повторить capability eval внутри контейнеров.

## Blockers

- Docker Desktop proxy `http.docker.internal:3128` не отдаёт слои: `docker pull` зависает для Docker Hub, ECR и локального hubproxy. Локальный PostgreSQL/e2e подтверждает приложение вне контейнера.

## Non-goals

- OCR для изображений и сканированных PDF.
- SSO, RBAC, ACL на уровне отдельных документов.
- Высокодоступный кластер и горизонтальное масштабирование worker.

## Verification

```bash
python3 -m pytest tests/test_chunking.py tests/test_extractors.py tests/test_fusion.py tests/test_prompting.py
# 10 passed in 0.01s — 2026-08-04

.venv/bin/pytest --cov=rag_app --cov-report=term-missing
# 36 passed, 2 skipped; 82.99% — 2026-08-04

TEST_DATABASE_URL=postgresql+psycopg://... .venv/bin/pytest -m integration tests/test_postgres_e2e.py
# 1 passed — PostgreSQL 17 + pgvector 0.8

RUN_LIVE_GIGACHAT=1 .venv/bin/pytest -m live tests/test_gigachat_live.py
# 1 passed — Embeddings-2 + GigaChat-2-Pro
```
