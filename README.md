# Hestia

> *Guarding the flame beyond Earth.*

Hestia is an AI-powered knowledge dashboard that **summarizes, ranks and explains** decades of
NASA microgravity combustion experiments (BASS, Saffire, SAME, FLEX, ACME) to inform **fire safety
for Moon and Mars missions**. It is named after the Greek goddess of the hearth, who kept the
home fire under control.

Every AI answer is grounded in NASA sources and cites them (`[NTRS-ID, p.X]`). When the sources
don't contain the answer, Hestia says so.

Built by **black-vortex** (Douala, Cameroon) for the NASA Space Apps Challenge 2026,
challenge *Flame in Freefall: AI-Powered Fire Safety Insights from Microgravity Combustion Data*.

> **Status: Phase 1 (foundation).** Infrastructure, scaffolding and data tooling only. The API
> returns placeholder data marked `[MOCK]`. Product logic is built during the hackathon. The full
> brief is in [PROJECT_SPEC.md](PROJECT_SPEC.md).

## Architecture

```
  NTRS API ──► pipeline/fetch_ntrs ──► data/ntrs/pdf ──► pipeline/extract_text ──► data/ntrs/text
  PSI (manual) ─► data/psi                                      │
  FLEX Table IX ─► data/flex/*.csv                              ▼
                                       pipeline/chunk ─► pipeline/embed ─► pipeline/ingest
                                                                                │
                                                                                ▼
 ┌──────────────────────┐   HTTP/JSON   ┌──────────────────────────┐   SQL   ┌─────────────────────┐
 │ web/  Next.js (3000) │ ────────────► │ backend/ FastAPI (8000)  │ ──────► │ PostgreSQL 16       │
 │ Tailwind · Recharts  │ ◄──────────── │ routers · services/llm   │         │ + pgvector (5434)   │
 │ React Three Fiber    │  typed via    │ services/retrieval       │         │ docker compose      │
 └──────────────────────┘  OpenAPI      └────────────┬─────────────┘         └─────────────────────┘
                                                     │ LLM_PROVIDER
                                                     ▼
                                     mock │ openai │ gemini │ anthropic
```

| Layer | Stack |
|---|---|
| Frontend | Next.js (App Router) · TypeScript strict · Tailwind CSS · Recharts · React Three Fiber · pnpm |
| API | Python 3.12 · FastAPI · Pydantic v2 · uv · ruff |
| Database | PostgreSQL 16 + pgvector · SQLAlchemy 2 · Alembic |
| Data | PyMuPDF · pandas · scikit-learn |

## Quick start

Prerequisites: Docker, [uv](https://docs.astral.sh/uv/), Node 24+ with pnpm, and `make`
(on Windows: `winget install ezwinports.make`, then use Git Bash).

```bash
cp .env.example .env
make install           # uv sync + pnpm install
make up migrate seed   # Postgres + pgvector, tables, mock rows
make api               # terminal 1 → http://localhost:8000/docs
make web               # terminal 2 → http://localhost:3000
```

Everything runs with `LLM_PROVIDER=mock`, with no API key needed.

### Other commands

| Command | What it does |
|---|---|
| `make fetch` | Download the NTRS catalog + PDFs into `data/ntrs/` |
| `make extract` | Per-page text + `extraction_report.csv` |
| `make lint` | ruff + eslint + tsc |
| `make test` | Backend tests |
| `make types` | Regenerate `web/src/lib/api-types.ts` (API must be running) |
| `make down` | Stop Postgres |

## API (Phase 1: mock data)

| Method | Route | Purpose |
|---|---|---|
| GET | `/health` | `{status, db}` with a real DB check |
| GET | `/experiments` | List; filters `fuel`, `gravity`, `outcome`, `o2_min`, `o2_max` |
| GET | `/experiments/{code}` | Detail + test runs + findings + sources |
| GET | `/compare?codes=A,B` | Side-by-side comparison |
| GET | `/ranking?target=moon\|mars` | Findings ranked by relevance |
| POST | `/ask` | `{question}` → `{answer, citations, insufficient_data}` |
| POST | `/predict` | `{fuel, oxygen_percent, pressure_kpa, initial_diameter_mm}` → `{burn_rate_k, extinction_probability}` |

Experiment routes read from the database and fall back to built-in mock data if it is empty or
unreachable.

## Repository layout

```
backend/   FastAPI app (app/), Alembic migrations, data pipeline (pipeline/), tests
web/       Next.js app: one route per screen, src/lib/api.ts typed client
data/      Datasets. See data/README.md for how to obtain each one
```

## Team

| Member | Role |
|---|---|
| _TBD_ | Team lead / pitch |
| _TBD_ | Backend & data pipeline |
| _TBD_ | AI / RAG |
| _TBD_ | Frontend & 3D |
| _TBD_ | Design (Figma) |

Workflow: `main` is protected; work on `feat/<name>` branches and merge at each milestone.
Conventional commits (`feat:`, `fix:`, `chore:`, `docs:`).

## Data sources

- **NASA Technical Reports Server (NTRS)**: <https://ntrs.nasa.gov> · API docs: <https://ntrs.nasa.gov/api/openapi/>
- **NASA Physical Sciences Informatics (PSI)**: <https://psi.nasa.gov>
- **FLEX detailed results**: NASA/TP-2015-216046, Table IX (manually transcribed)

See [data/README.md](data/README.md) for download and transcription steps.

## License

NASA data is in the public domain (NTRS) or released under CC0 (PSI). Hestia is not endorsed by
NASA. A license for the code is still to be chosen by the team.
