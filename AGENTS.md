# Repository Guidelines

## Project Structure & Module Organization

This repository is currently a configuration-only scaffold: no application source, tests, dependency manifest, or build scripts have been committed. Add production code under `src/`, mirror its modules under `tests/`, and keep reusable prompts or sample documents in `assets/`. Put one-off developer utilities in `scripts/`; do not mix them with runtime modules.

The existing ` .env` filename contains a leading space. Treat it as local-only configuration and normalize it to `.env` when the project is bootstrapped. Commit a redacted `.env.example` instead of credentials.

## Build, Test, and Development Commands

There is no runnable toolchain yet. The first implementation change should add a dependency manifest and expose a small, stable command surface through a `Makefile`:

- `make setup` — install development dependencies.
- `make run` — start the local RAG application or service.
- `make test` — run the complete automated test suite.
- `make lint` — run formatting, linting, and static checks.

Keep these targets thin wrappers around the selected ecosystem tools, and update this guide when they become available. Contributors should not rely on undocumented, machine-specific commands.

## Coding Style & Naming Conventions

Use the formatter and linter declared by the eventual project configuration; checked-in formatting is authoritative. Prefer small modules with explicit interfaces between ingestion, retrieval, model-provider, and response-generation code. Use `snake_case` for Python files, functions, and variables, `PascalCase` for classes, and descriptive names such as `document_chunker.py`. Keep provider-specific logic behind adapters rather than branching throughout the codebase.

## Testing Guidelines

Place tests in `tests/` and name them `test_<module>.py`. Cover normal behavior, empty inputs, provider failures, and retrieval edge cases. Tests must not call paid or external LLM endpoints by default; use fixtures or fakes, with live integration tests explicitly marked and opt-in.

## Commit & Pull Request Guidelines

No Git history is available in this workspace, so no existing convention can be inferred. Until one is established, use concise imperative Conventional Commits, for example `feat: add vector-store adapter` or `test: cover empty retrieval result`. Pull requests should explain the motivation, summarize behavior changes, list verification commands, link relevant issues, and include sample output or screenshots when user-visible behavior changes.

## Security & Configuration

Never commit API keys or populated environment files. Document required variables in `.env.example`, use placeholders, and redact model responses or logs before sharing them.
