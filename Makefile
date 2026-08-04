.PHONY: setup run stop logs demo test lint format

setup:
	python3 -m venv .venv
	.venv/bin/python -m pip install --upgrade pip
	.venv/bin/python -m pip install --requirement requirements.lock
	.venv/bin/python -m pip install --no-deps --editable .

run:
	docker compose up --build

stop:
	docker compose down

logs:
	docker compose logs -f api worker

demo:
	docker compose run --rm api python -m rag_app.seed

test:
	docker compose run --rm -e LLM_PROVIDER=fake api pytest --cov=rag_app --cov-report=term-missing

lint:
	docker compose run --rm --no-deps api ruff check src tests
	docker compose run --rm --no-deps api mypy src

format:
	docker compose run --rm --no-deps api ruff format src tests
	docker compose run --rm --no-deps api ruff check --fix src tests
