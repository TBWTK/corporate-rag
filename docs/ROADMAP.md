---
title: Этапы проекта
type: roadmap
status: complete
updated: 2026-08-10
---

# Этапы проекта

| Этап | Проверяемый результат | Критерий завершения | Статус |
| --- | --- | --- | --- |
| Audit | Требования, лимиты GigaChat, риски и критерии качества описаны | `AUDIT.md`, `QUALITY.md`, официальный source review | done |
| Domain | Парсинг, chunking, fusion и prompt имеют test-first контракты | Unit suite зелёный | done |
| Product | API, worker, pgvector и web UI работают вместе | Docker e2e upload → ready → chat | done |
| Quality | Форматы, API, DB, безопасность и UI проверены | pytest, coverage, Ruff, mypy, browser QA | done |
| Live | Реальный GigaChat подтверждён малым smoke-тестом | Один embedding и один grounded answer | done |
| Handoff | Документация совпадает с кодом, Git чист | project-control audit и финальный commit | done |
| Extended demo | 20 связанных файлов и уточняющий диалог работают end-to-end | corpus audit + two-turn Docker chat + docs | done |
| Visual instructions | PDF/DOCX-скриншоты превращаются в шаги и превью источников | 7 файлов, 44 страницы, offline tests и browser QA | done |
| Visual answer UX | Неоднозначный запрос уточняется, ответ остаётся пошаговым, источники компактны | live Outlook/iOS flow + cited-page grouping + browser QA | done |
| Document relations | Подтверждённые типизированные связи безопасно расширяют hybrid retrieval | API/UI + one-hop limits + PostgreSQL/browser QA | done |
| Beginner instructions | DOCX-ссылки и visual-шаги дают новичку полный проверяемый сценарий | exact URL + four-section answer + source-page browser QA | done |
| Inline visual tutorial | Процитированные страницы видны прямо под ответом без смешивания файлов | one-file auto gallery + multi-file choice + desktop/mobile QA | done |

Допустимые статусы: `planned`, `active`, `blocked`, `done`.
