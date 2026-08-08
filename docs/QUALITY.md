---
title: Качество
type: quality
status: active
updated: 2026-08-08
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
| Когда мне обязательно быть в офисе? → «Я из финансов» | Пн–Чт и последние 3 рабочих дня месяца | work format + finance agreement |
| Какой график у L2 поддержки? | 2/2, 08:00–20:00; до 2 удалённых дневных смен | support agreement + XLSX |
| Кто согласует CRM? → «Я из продаж» | руководитель + Sales Operations, 2 рабочих дня | access guide + systems CSV |
| Что изучает новый инженер? | общие тренинги, наставник, GitLab, первая задача | onboarding HTML/MD + XLSX |

Успех: ответ содержит правильный факт, хотя бы одну корректную цитату и не добавляет неподтверждённое правило. Нерелевантный вопрос должен вернуть формулировку о недостаточности данных.

## Regression gates

- [x] Test-first unit: chunking, extractors TXT/MD/CSV, RRF, prompt.
- [x] Extractor tests: PDF, DOCX, XLSX, PPTX, HTML.
- [x] API integration: spaces, upload, statuses, chat, duplicate, delete.
- [x] DB integration: pgvector DDL, ingestion и hybrid ranking.
- [x] Coverage не ниже 80% ветвей: 83,96% (`57 passed`, `2 skipped`).
- [x] Ruff и strict mypy.
- [x] Browser QA desktop и mobile 390×844, console чистая.
- [x] Live smoke отдельно от CI: один synthetic embedding и короткий вопрос.
- [x] Корпус: ровно 50 извлекаемых файлов, 8 форматов, 10 связанных соглашений.
- [x] Кейс-реестр: 36 уникальных сценариев, по 12 `answer`/`clarification`/`two_turn`,
  с существующими `source_files`.
- [x] Clarification contract: JSON parsing, 2–5 вариантов, fallback и contextual follow-up.
- [x] Visual artifact QA: все страницы DOCX/PDF, листы XLSX и слайды PPTX; overflow отсутствует.
- [x] Vision ingestion: visual detection, PDF/DOCX render, JSON-to-step normalization, provider
  file lifecycle, text fallback, ordered context expansion и source image endpoint покрыты офлайн.
- [x] Instruction corpus render: 7 пользовательских файлов, 44/44 страницы, 56 встроенных
  изображений; порядок страниц и читаемость проверены по PNG.
- [x] Visual-answer UX: неоднозначная инструкция требует выбора сценария, API объединяет цитаты
  одной страницы, UI сначала показывает три свёрнутых источника и лениво загружает изображения.

## Результаты расширенного демо

- Seed: 30 новых файлов добавлены к 20 исходным; 50 документов имеют статус `ready`, создано
  70 чанков, дубликатов имён нет; повторный запуск добавил 0.
- При обновлении seed удалены семь устаревших бинарных ревизий демо-файлов; актуальные версии
  сохранены, поэтому в пространстве осталась ровно одна версия каждого из 50 документов.
- PostgreSQL integration: 50 файлов загружены, проиндексированы и участвуют в hybrid retrieval.
- Live work-format flow: вопрос об обязательном офисе → пять вариантов подразделения →
  финансовый контроль → Пн–Чт и последние три рабочих дня месяца с цитатой допсоглашения.
- Live regression: ответы провайдера с более чем пятью вариантами нормализуются до четырёх
  конкретных и обобщающего «Другое»; UI-контракт закреплён unit-тестом и prompt.
- Live procurement flow: 600 000 ₽ → уточнение OpEx/CapEx → CapEx → комиссия и CFO с CSV/PPTX-цитатами.
- UI: desktop и 390×844, кнопки не выходят за viewport, console warnings/errors отсутствуют.
- Live visual flow: общий запрос о мобильной почте → выбор Outlook/iOS → 13 шагов Outlook;
  11 процитированных страниц вместо 35 фрагментов, по умолчанию видны три, изображения не
  загружаются до раскрытия карточки.

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
- Visual instruction: до 100 страниц на документ, 144 DPI, render timeout 120 секунд;
  последовательный контекст ответа — до 40 chunks.
- Ошибки не содержат credential или access token.
