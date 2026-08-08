---
title: Текущее состояние
type: state
status: complete
updated: 2026-08-08
---

# Текущее состояние

## Active objective

Добавить безопасную типизированную связность документов: владелец знаний явно подтверждает связь,
а retrieval ограниченно добавляет релевантные фрагменты связанных документов, не вытесняя
результаты hybrid search.

## Acceptance criteria

- [x] Связь хранит направление, один из разрешённых типов, evidence и статус; self-link,
  cross-space, неготовые документы и дубликаты отклоняются.
- [x] Только `confirmed`-связи участвуют в retrieval; предложенная или случайно похожая связь не
  меняет контекст ответа.
- [x] Graph expansion выполняет один переход, добавляет не более трёх документов и только
  релевантные chunks; исходный top-k hybrid search сохраняет порядок и состав.
- [x] API позволяет создать, просмотреть и удалить связь в пределах пространства; удаление
  документа каскадно удаляет его связи.
- [x] Web UI позволяет связать два готовых документа, показывает тип/направление связи и позволяет
  удалить её без ручного обращения к API.
- [x] Источник ответа помечает graph provenance, когда chunk был добавлен через связь.
- [x] Офлайн-тесты, PostgreSQL integration, `make test`, `make lint`, browser QA и
  project-control audit проходят.

## Current verified state

- Базовый retrieval по-прежнему использует pgvector cosine + Russian FTS + RRF и сохраняет
  исходный top-6 seed-набор до graph expansion.
- Предыдущий visual-answer этап закрыт: `57 passed`, `2 skipped`, coverage 83,96%, browser QA пройден.
- Добавлена adjacency-таблица `document_relations` с типом, статусом, evidence, направлением,
  уникальностью и запретом self-link.
- API unit-проверка подтвердила create/list/delete, каскад при удалении документа и отклонение
  duplicate, cross-space, self-link, invalid type и документов не в статусе `ready`.
- Retrieval unit-проверка подтвердила один переход, лимит соседей, сохранение seed-порядка,
  игнорирование `suggested` и graph provenance в source payload; целевые `19 passed`.
- PostgreSQL integration в отдельной временной БД подтвердил API relation и реальный pgvector
  expansion; тестовая БД удалена, пространство демо не изменено.
- Browser QA подтвердил создание, направленное отображение и удаление связи через UI; временная
  связь удалена, API списка вернул `[]`.
- Полный regression: `61 passed`, `2 skipped`, branch coverage 84,83%; Ruff и strict mypy прошли.
- Worktree содержит незакоммиченные изменения предыдущего демо-этапа; они сохраняются.

## Changed areas

- Добавлены DB model/schema relations, CRUD API, bounded retrieval expansion, graph provenance,
  web UI и regression/integration tests.
- Ingestion извлечения текста, embedding model и базовый hybrid search не изменены.

## Decisions made

- Граф реализуется обычной adjacency-таблицей PostgreSQL; отдельная graph DB не нужна.
- Hybrid retrieval остаётся источником seed chunks; graph expansion выполняется после него и не
  удаляет seed-результаты.
- Автоматическое сходство имени/текста не создаёт `confirmed`-связь. В текущем этапе связь явно
  создаёт пользователь; статус `suggested` зарезервирован и не участвует в retrieval.
- Расширение симметрично для поиска, хотя смысл связи хранится направленно.

## Next exact step

Этап закрыт; ждать следующего продуктового запроса пользователя.

## Blockers

- Нет.

## Non-goals

- Автоматическое подтверждение связей по имени файла, embedding similarity или выводу LLM.
- Многошаговый обход графа, отдельная graph DB и полнотекстовый knowledge graph сущностей.
- Версионное нормотворчество и юридическая гарантия приоритета документов.
- Изменение embedding model, повторная индексация корпуса, SSO/RBAC.

## Verification

```bash
.venv/bin/pytest -q tests/test_document_relations.py tests/test_retrieval_search.py tests/test_api.py
make test
make lint
docker compose exec -T db createdb -U rag rag_relation_test
docker compose run --rm -e LLM_PROVIDER=fake \
  -e TEST_DATABASE_URL=postgresql+psycopg://rag:rag-local-only@db:5432/rag_relation_test \
  api pytest -q -m integration
docker compose exec -T db dropdb -U rag rag_relation_test
python3 /Users/tbwtk/.codex/skills/project-control/scripts/project_control.py audit .
```
