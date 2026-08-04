---
title: Качество
type: quality
status: active
updated: 2026-08-04
---

# Качество

## Capability evals

Демо-корпус `examples/acme-corp` задаёт проверяемые вопросы:

| Вопрос | Обязательный факт | Ожидаемый источник |
| --- | --- | --- |
| Какой лимит гостиницы в Москве? | 10 000 ₽ за ночь | `travel_policy.txt` или `expense_limits.csv` |
| Когда подать заявление на отпуск? | за 14 календарных дней | `employee_handbook.md` |
| Когда сообщать об утечке? | в течение 15 минут | `information_security.md` |
| Кто согласует поездку свыше 100 000 ₽? | финансовый директор | travel + limits |

Успех: ответ содержит правильный факт, хотя бы одну корректную цитату и не добавляет неподтверждённое правило. Нерелевантный вопрос должен вернуть формулировку о недостаточности данных.

## Regression gates

- [x] Test-first unit: chunking, extractors TXT/MD/CSV, RRF, prompt.
- [x] Extractor tests: PDF, DOCX, XLSX, PPTX, HTML.
- [x] API integration: spaces, upload, statuses, chat, duplicate, delete.
- [x] DB integration: pgvector DDL, ingestion и hybrid ranking.
- [x] Coverage не ниже 80% ветвей: 82,99%.
- [x] Ruff и strict mypy.
- [x] Browser QA desktop и mobile 390×844, console чистая.
- [x] Live smoke отдельно от CI: один synthetic embedding и короткий вопрос.

## Verification commands

```bash
make test
make lint
docker compose up --build -d
docker compose run --rm api python -m rag_app.seed
curl -fsS http://localhost:8000/api/health
```

## Нефункциональные требования

- Файл: не более 25 МБ; расширение из allowlist; имя нормализуется.
- Embedding chunk: до 1100 символов с overlap 160, batch 8.
- Retrieval: 18 кандидатов на канал, top-6 после RRF.
- Generation: `temperature=0.1`, максимум 1200 output tokens.
- Никаких платных/live-вызовов в обычном pytest.
- Ошибки не содержат credential или access token.
