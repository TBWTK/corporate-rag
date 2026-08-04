---
title: Текущее состояние
type: state
status: complete
updated: 2026-08-04
---

# Текущее состояние

## Active objective

Завершено: демо-пространство Acme расширено связанным разноформатным корпусом, а чат структурированно уточняет подразделение, категорию сотрудника или вид расхода.

## Acceptance criteria

- [x] В `examples/acme-corp/` добавлены 16 связанных документов; всего 20 файлов и представлены все 8 поддерживаемых форматов.
- [x] Семь дополнительных соглашений задают область действия, приоритет и дату вступления в силу.
- [x] API структурированно возвращает `response_type=clarification`, один вопрос и 2–5 вариантов без выдуманного ответа.
- [x] Ответ пользователя в том же `conversation_id` разрешает неоднозначность и учитывается в retrieval/history.
- [x] Web UI показывает варианты уточнения как доступные кнопки и отправляет выбранный вариант в текущий диалог.
- [x] `examples/demo_cases.json` содержит обычные, неоднозначные и двухходовые проверяемые кейсы.
- [x] Seed индексирует 20/20 документов и остаётся идемпотентным: первый запуск добавил 16 к существующим 4, повторный — 0.
- [x] Unit, integration, Docker E2E, Ruff, mypy и визуальная проверка новых артефактов проходят.
- [x] Русская документация описывает корпус, уточняющий flow и результаты проверок.

## Current verified state

- Корпус содержит 20 `ready` документов и 29 фрагментов в TXT, Markdown, CSV, HTML, DOCX, PDF, XLSX и PPTX; семь файлов — дополнительные соглашения.
- Standard Docker suite: `44 passed, 2 skipped`, branch coverage 84,20%; Ruff и strict mypy зелёные.
- PostgreSQL integration-test индексирует 20 файлов в изолированной временной БД и проходит; временная БД удалена.
- Live GigaChat flow подтверждён дважды: remote work → sales → 3 дня; закупка 600 000 ₽ → CapEx → комиссия + CFO.
- Browser QA desktop и 390×844: кнопки уточнения доступны и кликабельны, console warnings/errors — 0.
- DOCX/PDF/XLSX/PPTX отрендерены полностью; даты XLSX и перенос PPTX исправлены после visual review, `slides_test.py` не нашёл overflow.

## Changed areas

- Изменены `generation/`, `services/chat.py`, API schemas/routes и web UI.
- Добавлены 16 файлов в `examples/acme-corp/`, `examples/demo_cases.json`, генераторы артефактов и тесты корпуса/диалога.
- Синхронизированы `README.md`, `ARCHITECTURE.md`, `DATA.md`, `QUALITY.md`, `USER_GUIDE.md` и каталог `examples/README.md`.

## Decisions made

- PostgreSQL/pgvector и гибридный RRF вместо in-memory vector store.
- `Embeddings-2`/1024 как фиксированная индексная схема; `GigaChat-2-Pro` для ответа.
- PostgreSQL advisory lock сериализует GigaChat между API и worker.
- Compose использует `RAG_LLM_PROVIDER`, чтобы legacy-переменная `LLM_PROVIDER` в существующем `.env` не отключала GigaChat.
- Уточнение должно быть явным типом ответа, а не эвристикой UI; fallback на обычный текст сохраняет совместимость с провайдерами.

## Next exact step

При следующем этапе начать с нового objective и свежей верификации текущего `main`.

## Blockers

- Нет.

## Non-goals

- OCR для изображений и сканированных PDF.
- SSO, RBAC, ACL на уровне отдельных документов.
- Высокодоступный кластер и горизонтальное масштабирование worker.
- Автоматическое юридическое толкование противоречий без подтверждения пользователя.

## Verification

```bash
python3 -m pytest tests/test_chunking.py tests/test_extractors.py tests/test_fusion.py tests/test_prompting.py
# baseline

.venv/bin/pytest -q tests/test_clarification.py tests/test_prompting.py tests/test_api.py
# 11 passed — 2026-08-04

.venv/bin/pytest -q tests/test_demo_corpus.py
# 3 passed; 20 документов, 8 форматов, 7 соглашений, 12 кейсов — 2026-08-04

make test
# 44 passed, 2 skipped; branch coverage 84.20% — Python 3.12.13, 2026-08-04

make lint
# Ruff clean; mypy: no issues in 30 source files — 2026-08-04

TEST_DATABASE_URL=postgresql+psycopg://.../rag_test_clarification_20260804 \
  pytest -m integration tests/test_postgres_e2e.py
# 1 passed; 20 documents — 2026-08-04

curl -X POST http://localhost:8000/api/chat ...
# clarification(2 options) → capital expense → answer + CSV/PPTX citations

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
