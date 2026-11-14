.PHONY: check-llm up down migrate api web seed fetch extract flex ingest ingest-ntrs ingest-psi ingest-all ingest-status psi-corpus calibrate eval eval-retrieval lint test test-integration types install

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

check-llm:       ## live test of your keys/models: chat JSON, embeddings, vector size
	$(BACKEND) uv run python -m pipeline.check_providers

ingest:           ## load everything (NTRS + PSI + experiments + findings); resumable; ARGS=--force re-embeds in place
	$(BACKEND) uv run python -m pipeline.ingest $(ARGS)

ingest-all: ingest ## alias of `ingest`

ingest-ntrs:      ## NTRS reports only (chunk + embed); ARGS=--force / --pause 4 / --batch-size 20
	$(BACKEND) uv run python -m pipeline.ingest --only ntrs $(ARGS)

ingest-psi:       ## PSI corpus only (data/psi_corpus/out/chunks.jsonl)
	$(BACKEND) uv run python -m pipeline.ingest --only psi $(ARGS)

ingest-status:    ## what is indexed, with which embeddings, dimension check
	$(BACKEND) uv run python -m pipeline.ingest --status

psi-corpus:       ## rebuild data/psi_corpus/out from the sources (only needed to regenerate it)
	python data/psi_corpus/scripts/build_corpus.py --max-chars 1800

eval-retrieval:   ## retrieval quality on data/eval/questions.json (embeddings only)
	$(BACKEND) uv run python -m pipeline.evaluate --retrieval-only $(ARGS)

eval:             ## retrieval + answers + citations (calls the LLM); ARGS="--out report.json"
	$(BACKEND) uv run python -m pipeline.evaluate $(ARGS)

calibrate:        ## top-1 similarity of answerable vs out-of-corpus questions -> RETRIEVAL_MIN_SCORE
	$(BACKEND) uv run python -m pipeline.evaluate --calibrate

lint:             ## ruff + eslint + tsc
	$(BACKEND) uv run ruff check . && uv run ruff format --check .
	$(WEB) pnpm lint && pnpm typecheck

test:             ## backend tests (PostgreSQL integration tests are skipped without HESTIA_TEST_DATABASE_URL)
	$(BACKEND) uv run pytest

test-integration: ## PostgreSQL + pgvector tests; needs a *_test database, see tests/integration/conftest.py
	$(BACKEND) uv run pytest tests/integration -v

types:            ## regenerate frontend API types (API must be running on :8000)
	$(WEB) pnpm gen:types
