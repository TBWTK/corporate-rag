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
| Какой лимит гостиницы в Москве для обычного сотрудника? | 10 000 ₽ за ночь | `travel_policy.txt` или `expense_limits.csv` |
| Когда подать заявление на отпуск? | за 14 календарных дней | `employee_handbook.md` |
| Когда сообщать об утечке? | в течение 15 минут | `information_security.md` |
| Кто согласует поездку свыше 100 000 ₽? | финансовый директор | travel + limits |
| Сколько дней я могу работать удалённо? | уточнить подразделение/регион | базовая политика + соглашения |
| Какой целевой бонус? → «Я из продукта» | сначала уточнение, затем 12% | bonus policy + product agreement |
| Кто согласует закупку на 600 000 ₽? | уточнить OpEx/CapEx | procurement CSV + PPTX |

Успех: ответ содержит правильный факт, хотя бы одну корректную цитату и не добавляет неподтверждённое правило. Нерелевантный вопрос должен вернуть формулировку о недостаточности данных.

## Regression gates

- [x] Test-first unit: chunking, extractors TXT/MD/CSV, RRF, prompt.
- [x] Extractor tests: PDF, DOCX, XLSX, PPTX, HTML.
- [x] API integration: spaces, upload, statuses, chat, duplicate, delete.
- [x] DB integration: pgvector DDL, ingestion и hybrid ranking.
- [x] Coverage не ниже 80% ветвей: 84,20% (`44 passed`, `2 skipped`).
- [x] Ruff и strict mypy.
- [x] Browser QA desktop и mobile 390×844, console чистая.
- [x] Live smoke отдельно от CI: один synthetic embedding и короткий вопрос.
- [x] Корпус: ровно 20 извлекаемых файлов, 8 форматов, 7 связанных соглашений.
- [x] Clarification contract: JSON parsing, 2–5 вариантов, fallback и contextual follow-up.
- [x] Visual artifact QA: все страницы DOCX/PDF, листы XLSX и слайды PPTX; overflow отсутствует.

## Результаты расширенного демо

- Seed: 16 новых файлов добавлены к четырём существующим; повторный запуск добавил 0; все 20 имеют статус `ready`.
- PostgreSQL integration: 20 файлов загружены, проиндексированы и участвуют в hybrid retrieval.
- Live remote flow: неоднозначный вопрос → 4 варианта → отдел продаж → 3 удалённых дня с цитатой.
- Live procurement flow: 600 000 ₽ → уточнение OpEx/CapEx → CapEx → комиссия и CFO с CSV/PPTX-цитатами.
- UI: desktop и 390×844, кнопки не выходят за viewport, console warnings/errors отсутствуют.

## Verification commands

```bash
make test
make lint
.venv/bin/pytest -q tests/test_demo_corpus.py tests/test_clarification.py
docker compose up --build -d
make demo
curl -fsS http://localhost:8000/api/health
```

## Нефункциональные требования

- Файл: не более 25 МБ; расширение из allowlist; имя нормализуется.
- Embedding chunk: до 1100 символов с overlap 160, batch 8.
- Retrieval: 18 кандидатов на канал, top-6 после RRF.
- Generation: `temperature=0.1`, максимум 1200 output tokens.
- Никаких платных/live-вызовов в обычном pytest.
- Ошибки не содержат credential или access token.
