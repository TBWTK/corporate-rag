---
title: ADR-001 — Embeddings-2 и vector(1024)
type: decision
status: accepted
updated: 2026-08-04
---

# ADR-001: фиксировать Embeddings-2 и `vector(1024)`

## Контекст

GigaChat предлагает Embeddings/Embeddings-2 с окном 512 токенов и 1024 координат и EmbeddingsGigaR с окном 4096 и 2560 координат. Размерность определяет DDL pgvector и тип ANN-индекса; смешивать модели в одном индексе нельзя.

## Решение

Первый релиз использует `Embeddings-2`, chunk до 1100 символов и HNSW `vector_cosine_ops` над `vector(1024)`. Модель и dimension валидируются вместе при старте.

## Последствия

Индекс компактен, поддерживается стандартным HNSW pgvector, а короткие chunks дают точные citations. Цена — меньший контекст одного embedding и обязательная полная миграция/reindex для GigaR. Переход рассматривается только после retrieval eval, а не по субъективному впечатлению.
