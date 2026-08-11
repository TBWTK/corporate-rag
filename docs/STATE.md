---
title: Текущее состояние
type: state
status: complete
updated: 2026-08-11
---

# Текущее состояние

## Active objective

Подготовить передаваемый заказчику полностью локальный контур на Ollama: приложение должно без
GigaChat и API-ключей выполнять embeddings, генерацию grounded-ответов и vision-разбор страниц, а
оператор — запустить и проверить его по одному пошаговому гайду для macOS или Windows.

## Acceptance criteria

- [x] `LLM_PROVIDER=ollama` использует нативные Ollama `/api/embed` и `/api/chat`, поддерживает
  отдельную vision-модель, JSON-ответы, base64-изображения, настраиваемые timeout/context/keep-alive
  и безопасные ошибки.
- [x] Factory запускает Ollama без credential и при необходимости сериализует вызовы API/worker;
  GigaChat и fake-режимы не меняют поведение.
- [x] Готовый `.env.ollama.example` совместим с текущим `vector(1024)` и Docker Desktop на macOS и
  Windows; рекомендуемый набор рассчитан на ноутбук с 32 ГБ RAM.
- [x] Оператор имеет одну команду самопроверки доступности Ollama, embedding-размерности и chat;
  проверка завершается понятной диагностикой.
- [x] Отдельный гайд покрывает установку Docker Desktop и Ollama, загрузку моделей, настройку host
  access и local-only режима, запуск, первый документ/вопрос, обновление, reindex, остановку,
  troubleshooting и ограничения отдельно для macOS и Windows.
- [x] Архитектура, README, quality, roadmap и ADR отражают локальный контур и запрет смешивания
  embeddings разных моделей.
- [x] Unit/provider contract tests, полный `make test`, `make lint`, compose config и
  project-control audit проходят.

## Current verified state

- До задачи factory поддерживал только `gigachat` и `fake`; отдельного Ollama HTTP adapter не было.
- Интерфейс `ModelProvider` уже разделяет `embed`, `generate` и опциональный `analyze_image`, поэтому
  локальный backend можно добавить без ветвления в ingestion/retrieval/chat.
- PostgreSQL хранит `vector(1024)`. `mxbai-embed-large` нативно возвращает 1024 измерения и не
  требует миграции схемы, но существующие embeddings другой модели требуют полной переиндексации.
- Официальный Ollama API предоставляет batch `/api/embed`, chat с `format=json`, vision через
  base64 `images`; Docker Desktop обращается к host service через `host.docker.internal`.
- Для целевого 32-ГБ ноутбука выбраны `qwen3:8b` (5,2 ГБ), `mxbai-embed-large` (670 МБ) и
  `qwen2.5vl:3b` (3,2 ГБ); фактическая скорость зависит от CPU/GPU и объёма документов.
- Ollama на машине разработки не установлен; live-модель не скачивается автоматически. Контракт
  проверен mock HTTP и сетевым stub smoke без внешних токенов.
- Реализован `OllamaProvider` с batch embed, JSON chat, отдельным vision model, base64 images,
  dimension check и безопасными ошибками; factory поддерживает локальную сериализацию.
- Добавлены `.env.ollama.example`, `rag_app.local_check`, `make local-check` и переключаемый
  `RAG_ENV_FILE` в Compose; local compose config и 21 целевой тест прошли.
- Добавлен полный `docs/LOCAL_MODELS.md`, ADR-003; provider-neutral flows и правила reindex/security
  отражены в README, architecture, data, security, audit, quality и roadmap.
- Container preflight с локальным профилем корректно сообщил о недоступном Ollama; затем тот же
  image через `host.docker.internal` прошёл сетевой stub smoke: три модели, embed 1024 и JSON chat.
- Полный regression: `81 passed`, `2 skipped`, branch coverage 84,98%; Ruff, strict mypy,
  compose config, `git diff --check` и project-control audit прошли.
- Исходное состояние: `main` совпадает с `origin/main`, worktree чистый.

## Changed areas

- Изменены provider/config/factory, ingestion error, Compose/Makefile, env-шаблоны, operator check,
  tests и проектная/операторская документация.

## Decisions made

- Ollama запускается нативно на хосте для доступа к аппаратному ускорению; Docker-контейнеры
  приложения используют `host.docker.internal`, а не контейнер Ollama.
- Размерность индекса остаётся 1024; смена embedding-модели требует переиндексации, даже при той же
  размерности.
- На 32 ГБ используются умеренные quantized-модели и последовательные модельные вызовы; vision
  можно отключить для полностью текстового корпуса.

## Next exact step

Нет активной разработки; заказчик выполняет реальный inference smoke по `docs/LOCAL_MODELS.md`
после загрузки моделей.

## Blockers

- Нет блокеров для передачи. Реальная скорость/качество целевого ноутбука подтверждаются оператором
  после многогигабайтного `ollama pull`; это явно выделено в гайде.

## Non-goals

- Инструкция для Linux, автоматическая установка Ollama/Docker или автоматическое скачивание
  многогигабайтных моделей.
- Изменение pgvector-схемы, сравнительный benchmark качества либо гарантированный SLA на CPU.
- Публичная публикация портов, SSO/RBAC или production-hardening неаутентифицированного MVP.

## Verification

```bash
pytest -q tests/test_providers.py tests/test_config.py tests/test_local_check.py
docker compose config
make test
make lint
python3 /Users/tbwtk/.codex/skills/project-control/scripts/project_control.py audit .
```
