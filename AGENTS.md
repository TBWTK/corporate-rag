# Repository Guidelines

## Project Structure & Module Organization

Runtime code lives in `src/rag_app/`: `api/` exposes FastAPI routes, `ingestion/` and `services/` process documents, `retrieval/` performs hybrid search, `providers/` isolates model APIs, and `static/` contains the web UI. Tests mirror these boundaries under `tests/`. Keep reusable demonstration content in `examples/`, durable project state in `docs/`, and deployment entry points at the repository root.

## Build, Test, and Development Commands

- `make setup` — create `.venv` and install the package with developer tools.
- `make run` — build and start PostgreSQL, API, and ingestion worker with Docker Compose.
- `make demo` — enqueue the bundled Acme document set after services are running.
- `make test` — run pytest with branch coverage using the offline fake provider.
- `make lint` — run Ruff and strict mypy checks.
- `make stop` — stop containers without deleting persistent volumes.

Use `docker compose logs -f api worker` when diagnosing ingestion or provider failures.

## Coding Style & Naming Conventions

Target Python 3.12, four-space indentation, type annotations, and a 100-character line limit. Ruff formatting and lint output are authoritative. Use `snake_case` for modules/functions, `PascalCase` for classes, and explicit adapter names such as `GigaChatProvider`. Keep model, storage, and HTTP concerns behind their existing interfaces; do not add provider branching throughout domain code.

## Testing Guidelines

Name tests `test_<behavior>.py` and follow red-green-refactor. Cover success, empty input, corrupt formats, provider failure, and space isolation. Ordinary tests must never call paid endpoints; use `FakeProvider` or HTTP transports. Mark Docker-backed tests `integration` and token-consuming checks `live`. The coverage gate is 80% branch coverage.

## Commit, Push & Pull Request Guidelines

Use concise imperative Conventional Commits, matching `chore: initialize repository`; examples include `feat: add document retry` and `test: cover tenant boundary`. Pull requests must describe motivation, changed behavior, verification commands, issue links, and screenshots for UI changes. Never commit a failing default test suite.

The repository owner authorizes Codex to maintain Git and push cohesive verified changes directly to
`main`. Before every push, fetch `origin/main`, reject divergence instead of force-pushing, run the
relevant tests plus `make lint`, update durable documentation, and keep the worktree free of unrelated
or generated artifacts. Use a PR when review, an experimental branch, or external coordination is
actually useful; direct-to-main does not relax verification, secret scanning, or documentation gates.

## Security & Configuration

Never commit `.env`, API keys, access tokens, uploaded files, or database volumes. Add placeholders to `.env.example`. Treat extracted text as untrusted input, preserve the `space_id` filter on every retrieval, and do not expose this unauthenticated release outside a trusted network.

<!-- project-control:start -->
## Project continuity

- Before planning or editing, read `docs/README.md`, `docs/STATE.md`, and documents directly relevant to the task.
- Reconstruct state from repository files, Git diff/status, and fresh verification.
- Define acceptance criteria and non-goals before implementation.
- Work in verifiable checkpoints and update `docs/STATE.md` after each checkpoint.
- Keep one active objective and one exact next step in `docs/STATE.md`.
- Do not mark work complete without executable or inspectable evidence.
- Do not convert unfinished acceptance criteria into technical debt.
<!-- project-control:end -->
