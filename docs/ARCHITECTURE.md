---
title: Архитектура
type: architecture
status: active
updated: 2026-08-08
---

# Архитектура

## Контекст

Один локальный web-клиент обращается к FastAPI. API хранит метаданные и диалоги в PostgreSQL, а
файлы и изображения страниц — в Docker volume. Worker извлекает обычный текст; PDF/DOCX со
встроенными изображениями дополнительно рендерит постранично, разбирает через GigaChat Vision и
вызывает GigaChat Embeddings. На вопрос API выполняет hybrid retrieval, уточняет визуальный сценарий,
а затем ограниченно расширяет контекст по подтверждённым связям документов и вызывает GigaChat 2
Pro. Источники ответа строятся отдельно: только из процитированных chunks/страниц, с graph
provenance для фрагментов, добавленных через связь.

```mermaid
flowchart LR
  User["Сотрудник"] --> Web["Web UI"]
  Web --> API["FastAPI"]
  API --> DB[("PostgreSQL + pgvector")]
  API --> Files[("Volume документов")]
  Worker["Ingestion worker"] --> DB
  Worker --> Files
  Worker --> Render["Poppler + LibreOffice"]
  API --> Lock["PostgreSQL advisory lock"]
  Worker --> Lock
  Lock --> Giga["GigaChat API"]
```

## Инварианты

- Поиск никогда не пересекает границу `space_id`.
- Только `confirmed`-связи между двумя `ready`-документами одного space расширяют retrieval.
- Graph expansion выполняет один переход, не удаляет hybrid seeds и ограничен тремя соседями.
- Ответ получает только извлечённые фрагменты; контекст считается недоверенным.
- DOCX-гиперссылки извлекаются из OOXML relationships; разрешены только `http`, `https` и
  `mailto`, а UI делает кликабельными только проверенные `http`/`https` URL.
- Каждый пользовательский факт должен иметь цитату `[N]`; при нехватке данных модель сообщает об этом.
- Визуальная инструкция должна содержать «Перед началом», атомарные шаги, «Как проверить» и
  «Если не получилось»; критический URL нельзя заменять ссылкой на citation `[N]`.
- Если выбор правила зависит от отсутствующего атрибута, модель задаёт один вопрос с 2–5 вариантами, а не предполагает ответ.
- `.env`, ключи и access token не сохраняются в БД и не возвращаются API.
- Индекс создаётся одной моделью `Embeddings-2` размерности 1024.
- Вызовы GigaChat сериализуются между процессами для лимита одного потока.

## Компоненты и границы

| Компонент | Ответственность | Отказ |
| --- | --- | --- |
| Web UI | пространства, upload, polling, чат, источники | показывает безопасное сообщение API |
| API | валидация, метаданные, retrieval, generation | 4xx для входа, 502 для провайдера |
| Worker | claim, extract, render, vision, chunk, embed, status | документ получает `error`, доступен retry |
| PostgreSQL | очередь, relations, HNSW, FTS, диалоги | health становится degraded |
| GigaChat adapter | OAuth, embeddings, chat, image upload/analyze/delete | секреты редактируются, ошибка не маскируется |

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
  W->>W: extract
  W->>W: DOCX hyperlink relationships → exact link chunk
  opt PDF/DOCX содержит изображения
    W->>W: render страниц → PNG
    W->>G: upload PNG → vision JSON → delete remote file
    W->>W: JSON → упорядоченные шаги с номером страницы
  end
  W->>W: chunk ≤ 1100 chars
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
  opt найдено несколько visual-инструкций без явного приложения
    A-->>U: выбрать приложение/платформу
    U->>A: выбранный вариант + same conversation_id
  end
  A->>D: visual-шаги + native DOCX text + exact links (до 40 chunks)
  A->>D: confirmed relations от seed-документов (one hop, до 3 соседей)
  A->>D: до 2 релевантных chunks каждого соседа
  A->>G: guarded prompt + numbered sources
  G-->>A: JSON answer или clarification
  A->>A: instruction quality gate + one grounded repair
  A->>A: deterministic URL/citation and beginner-structure guarantees
  alt достаточно данных
    A->>A: процитированные chunks → уникальные страницы
    A->>D: question + answer + compact source metadata
    A-->>U: answer + compact sources + token usage
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
- [ADR-002: подтверждённые связи документов](decisions/ADR-002-confirmed-document-relations.md).
- Внешний LangChain не используется: явные адаптеры уменьшают скрытую связанность и упрощают eval.
