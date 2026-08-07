.PHONY: sync test lint format ingest train evaluate pipeline serve docker-build

sync:
	uv sync --frozen

test:
	uv run pytest --cov=reviewsignal --cov-report=term-missing

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff check --fix .
	uv run ruff format .

ingest:
	uv run reviewsignal ingest

train:
	uv run reviewsignal train

evaluate:
	uv run reviewsignal evaluate

pipeline:
	uv run reviewsignal pipeline

serve:
	uv run uvicorn reviewsignal.api:app --reload

docker-build:
	docker build -t reviewsignal:local .

