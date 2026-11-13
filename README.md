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

> **Status: Phase 2 (product).** Real data end to end: 55 NTRS reports indexed for retrieval,
> 276 FLEX droplet tests, 21 curated findings with verified page citations, and a model trained
> on FLEX. Grounded answers need an LLM key (Gemini recommended); without one the assistant
> quotes the top passages verbatim. The original brief is in [PROJECT_SPEC.md](PROJECT_SPEC.md).

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
cp .env.example .env    # then set LLM_PROVIDER=gemini and GEMINI_API_KEY
make install           # uv sync + pnpm install
make up migrate        # Postgres + pgvector, tables
make fetch extract     # NTRS catalog + PDFs + per-page text (~10 min)
make ingest            # chunk + embed documents, load experiments, FLEX runs, findings
make api               # terminal 1 → http://localhost:8000/docs
make web               # terminal 2 → http://localhost:3000
```

Everything also runs with `LLM_PROVIDER=mock` and no key: search falls back to keyword
matching and the assistant returns extractive answers. After adding a key, re-embed with
`make ingest ARGS=--force` (embeddings from different providers are not comparable).
`make seed` still inserts placeholder rows if you only want to see the UI.

### Other commands

| Command | What it does |
|---|---|
| `make fetch` | Download the NTRS catalog + PDFs into `data/ntrs/` |
| `make extract` | Per-page text + `extraction_report.csv` |
| `make flex` | Re-parse FLEX Table IX into `data/flex/flex_table_ix.csv` |
| `make ingest` | Load documents (chunk + embed), experiments, findings (`ARGS=--force` re-embeds) |
| `make lint` | ruff + eslint + tsc |
| `make test` | Backend tests |
| `make types` | Regenerate `web/src/lib/api-types.ts` (API must be running) |
| `make down` | Stop Postgres |

## API

| Method | Route | Purpose |
|---|---|---|
| GET | `/health` | `{status, db}` with a real DB check |
| GET | `/stats` | Knowledge-base counts for the overview |
| GET | `/experiments` | List; filters `fuel`, `gravity`, `outcome`, `o2_min`, `o2_max` |
| GET | `/experiments/{code}` | Detail + test runs + findings + sources |
| GET | `/compare?codes=A,B` | Side-by-side comparison |
| GET | `/compare/insights?codes=A,B` | Key differences with verified citations (LLM, cached) |
| GET | `/ranking?target=moon\|mars` | Findings ranked by relevance × confidence |
| POST | `/ask` | `{question, history?}` → `{answer, citations, insufficient_data}` |
| POST | `/predict` | `{fuel, oxygen_percent, pressure_kpa, initial_diameter_mm, co2_percent?, he_percent?}` → `{burn_rate_k, extinction_probability, droplet_lifetime_s, in_training_range}` |
| GET | `/predict/model` | Training size, cross-validated metrics, valid input ranges |

### How answers stay grounded

1. **Hybrid retrieval**: pgvector cosine similarity + Postgres full-text search, merged with
   reciprocal rank fusion. Chunks never cross a page, so every passage has an exact page.
2. **Generation**: the LLM sees only the retrieved passages and must cite `[NTRS-ID, p.X]`.
3. **Verification**: every citation is checked against the retrieved (document, page) pairs;
   anything else is removed. No relevant passage, or no surviving citation, means
   `insufficient_data: true`.

### The FLEX model

Trained at startup on `data/flex/flex_table_ix.csv`: ridge regression for the burning-rate
constant K (5-fold CV R² ≈ 0.70, MAE ≈ 0.05 mm²/s) and a degree-2 logistic regression for
extinction vs. complete burn (CV AUC ≈ 0.89). Inputs outside the tested ranges are flagged as
extrapolation. It describes ISS microgravity only.

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
