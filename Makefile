.PHONY: up down migrate api web seed fetch extract flex ingest lint test types install

BACKEND = cd backend &&
WEB = cd web &&

install:          ## install backend and frontend dependencies
	$(BACKEND) uv sync
	$(WEB) pnpm install

up:               ## start Postgres + pgvector
	docker compose up -d --wait db

down:             ## stop Postgres
	docker compose down

migrate:          ## run Alembic migrations
	$(BACKEND) uv run alembic upgrade head

api:              ## FastAPI with reload on :8000
	$(BACKEND) uv run uvicorn app.main:app --reload --port 8000

web:              ## Next.js dev server on :3000
	$(WEB) pnpm dev

seed:             ## insert mock rows using the mock LLM provider
	$(BACKEND) uv run python -m pipeline.ingest --mock

fetch:            ## fetch NTRS catalog + PDFs
	$(BACKEND) uv run python -m pipeline.fetch_ntrs

extract:          ## extract per-page text from PDFs
	$(BACKEND) uv run python -m pipeline.extract_text

flex:             ## parse FLEX Table IX from the extracted NTRS text into data/flex
	$(BACKEND) uv run python -m pipeline.flex_table

ingest:           ## load documents (chunk + embed), experiments and findings; ARGS=--force to re-embed
	$(BACKEND) uv run python -m pipeline.ingest $(ARGS)

lint:             ## ruff + eslint + tsc
	$(BACKEND) uv run ruff check . && uv run ruff format --check .
	$(WEB) pnpm lint && pnpm typecheck

test:             ## backend tests
	$(BACKEND) uv run pytest

types:            ## regenerate frontend API types (API must be running on :8000)
	$(WEB) pnpm gen:types
