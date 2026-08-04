---
title: Этапы проекта
type: roadmap
status: active
updated: 2026-08-04
---

# Этапы проекта

| Этап | Проверяемый результат | Критерий завершения | Статус |
| --- | --- | --- | --- |
| Audit | Требования, лимиты GigaChat, риски и критерии качества описаны | `AUDIT.md`, `QUALITY.md`, официальный source review | done |
| Domain | Парсинг, chunking, fusion и prompt имеют test-first контракты | Unit suite зелёный | done |
| Product | API, worker, pgvector и web UI работают вместе | Docker e2e upload → ready → chat | active |
| Quality | Форматы, API, DB, безопасность и UI проверены | pytest, coverage, Ruff, mypy, browser QA | done |
| Live | Реальный GigaChat подтверждён малым smoke-тестом | Один embedding и один grounded answer | done |
| Handoff | Документация совпадает с кодом, Git чист | project-control audit и финальный commit | planned |

Допустимые статусы: `planned`, `active`, `blocked`, `done`.
