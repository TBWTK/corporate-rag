---
title: Архитектура
type: architecture
status: active
updated: 2026-08-04
---

# Архитектура

## Контекст

Один локальный web-клиент обращается к FastAPI. API хранит метаданные и диалоги в PostgreSQL, а файлы — в Docker volume. Отдельный worker извлекает текст и вызывает GigaChat Embeddings. На вопрос API выполняет hybrid retrieval и вызывает GigaChat 2 Pro.

```mermaid
flowchart LR
  User["Сотрудник"] --> Web["Web UI"]
  Web --> API["FastAPI"]
  API --> DB[("PostgreSQL + pgvector")]
  API --> Files[("Volume документов")]
  Worker["Ingestion worker"] --> DB
  Worker --> Files
  API --> Lock["PostgreSQL advisory lock"]
  Worker --> Lock
  Lock --> Giga["GigaChat API"]
```

## Инварианты

- Поиск никогда не пересекает границу `space_id`.
- Ответ получает только извлечённые фрагменты; контекст считается недоверенным.
- Каждый пользовательский факт должен иметь цитату `[N]`; при нехватке данных модель сообщает об этом.
- Если выбор правила зависит от отсутствующего атрибута, модель задаёт один вопрос с 2–5 вариантами, а не предполагает ответ.
- `.env`, ключи и access token не сохраняются в БД и не возвращаются API.
- Индекс создаётся одной моделью `Embeddings-2` размерности 1024.
- Вызовы GigaChat сериализуются между процессами для лимита одного потока.

## Компоненты и границы

| Компонент | Ответственность | Отказ |
| --- | --- | --- |
| Web UI | пространства, upload, polling, чат, источники | показывает безопасное сообщение API |
| API | валидация, метаданные, retrieval, generation | 4xx для входа, 502 для провайдера |
| Worker | claim, extract, chunk, embed, status | документ получает `error`, доступен retry |
| PostgreSQL | очередь, версии, HNSW, FTS, диалоги | health становится degraded |
| GigaChat adapter | OAuth cache, embeddings, chat | секреты редактируются, ошибка не маскируется |

## Путь пользователя

```mermaid
journey
  title Путь от файлов к проверяемому ответу
  section Контекст
    Создать пространство: 5: Пользователь
    Перетащить связанные файлы: 5: Пользователь
    Дождаться статуса Готов: 3: Пользователь, Система
  section Вопрос
    Задать вопрос: 5: Пользователь
    Прочитать ответ: 5: Пользователь
    Раскрыть источники: 5: Пользователь
```

## Системный flow индексации

```mermaid
sequenceDiagram
  participant U as Web UI
  participant A as API
  participant D as PostgreSQL
  participant W as Worker
  participant G as GigaChat Embeddings
  U->>A: POST files
  A->>A: extension, size, SHA-256
  A->>D: document(status=queued)
  A-->>U: 202 Accepted
  W->>D: SELECT ... FOR UPDATE SKIP LOCKED
  W->>W: extract → chunk ≤ 1100 chars
  W->>G: batches of 8
  G-->>W: vectors[1024]
  W->>D: chunks + status=ready
  U->>A: polling documents
  A-->>U: ready
```

## Системный flow ответа

```mermaid
sequenceDiagram
  participant U as Web UI
  participant A as API
  participant D as PostgreSQL/pgvector
  participant G as GigaChat 2 Pro
  U->>A: question + space_id + conversation_id?
  A->>A: retrieval query = последние 2 сообщения + question
  A->>G: embedding(retrieval query)
  A->>D: vector top-N + Russian FTS top-N
  A->>A: Reciprocal Rank Fusion → top-6
  A->>G: guarded prompt + numbered sources
  G-->>A: JSON answer или clarification
  alt достаточно данных
    A->>D: question + answer + source metadata
    A-->>U: answer + sources + token usage
  else требуется атрибут
    A->>D: question + clarification
    A-->>U: clarification + 2–5 options
    U->>A: selected option + same conversation_id
    A->>A: contextual retrieval и повторная генерация
    A-->>U: grounded answer + sources
  end
```

## Latency и capacity

Upload отвечает после записи файла, не после embeddings. Индексация выполняется одним worker и ограничена внешним API. Chat включает query embedding, два SQL-поиска и generation; целевой бюджет для локального контура — до 30 секунд без формального SLO. HNSW рассчитан на 1024-мерные векторы; масштабная смена модели требует миграции.

## Значимые решения

- [ADR-001: Embeddings-2 и vector(1024)](decisions/ADR-001-embedding-and-vector-schema.md).
- Внешний LangChain не используется: явные адаптеры уменьшают скрытую связанность и упрощают eval.
