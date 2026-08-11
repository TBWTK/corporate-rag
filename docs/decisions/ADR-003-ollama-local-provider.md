---
title: "ADR-003: Ollama как локальный модельный backend"
type: decision
status: accepted
updated: 2026-08-11
---

# ADR-003: Ollama как локальный модельный backend

## Контекст

Заказчику нужен запуск на одном macOS/Windows-ноутбуке без внешнего API. Контур должен сохранить
hybrid retrieval, grounded generation и разбор визуальных инструкций, не дублируя доменную логику.

## Решение

Добавить `OllamaProvider` за существующими `ModelProvider`/`VisionModelProvider`. Ollama работает
нативно на хосте, а Docker Desktop обращается к нему через `host.docker.internal`. Используются
нативные `/api/embed` и `/api/chat`, JSON mode и base64 images. Вызовы API и worker по умолчанию
сериализуются PostgreSQL advisory lock.

Схема остаётся `vector(1024)`. Рекомендуемый embedding — `mxbai-embed-large`; любая смена
embedding-модели требует полной переиндексации. Локальный профиль не требует credential.

## Последствия

- GigaChat и Ollama взаимозаменяемы на границе provider, без ветвления retrieval/ingestion/chat.
- Нативный Ollama использует доступное ускорение, в отличие от Ollama внутри Docker Desktop на Mac.
- `OLLAMA_HOST=0.0.0.0:11434` расширяет поверхность локальной сети; оператор обязан блокировать
  внешний вход и не публиковать порт.
- Скорость и качество зависят от оборудования и выбранных весов; 32-ГБ профиль оптимизирует
  воспроизводимость MVP, а не максимальное качество.
