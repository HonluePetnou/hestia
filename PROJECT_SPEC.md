# PROJECT_SPEC — Hestia (NASA Space Apps 2026)

> Instructions for Claude Code. Read this whole file before writing any code.
> Your job in this session: **set up the repository foundation (Phase 1)**. Do NOT build the product features yet.

---

## 1. Context

- **Event:** NASA Space Apps Challenge 2026, Douala local event, November 14–15, 2026.
- **Product name:** **Hestia** — tagline: *"Guarding the flame beyond Earth."* Named after the Greek goddess of the hearth, who kept the home fire under control.
- **Team:** black-vortex (Douala, Cameroon).
- **Challenge:** *Flame in Freefall: AI-Powered Fire Safety Insights from Microgravity Combustion Data.*
- **Goal of the product:** an AI-powered knowledge dashboard that **summarizes, ranks and explains** decades of NASA microgravity combustion experiments to inform **fire safety for Moon and Mars missions**.
- **Core principle:** every AI answer must be grounded in NASA sources and show citations (`[NTRS-ID, p.X]`). If the sources do not contain the answer, the system says so. No hallucinated science.

### Data sources
| Source | Access | Use |
|---|---|---|
| NASA Technical Reports Server (NTRS) | Public API, no login. Search: `https://ntrs.nasa.gov/api/citations/search` — docs: `https://ntrs.nasa.gov/api/openapi/` — record page: `https://ntrs.nasa.gov/citations/<id>` | Papers and reports (PDF full text) for RAG |
| NASA Physical Sciences Informatics (PSI) | `https://psi.nasa.gov` — no documented public API, manual downloads, CC0 | Experiment metadata and test-condition tables (BASS, Saffire, SAME, FLEX, ACME) |
| FLEX detailed results (NASA/TP-2015-216046, Table IX) | Manual transcription to CSV | ~170 droplet combustion tests → small ML model (extinction / burn rate) + 3D simulator |

### Hackathon constraints
- All UI text and all project documentation in **English**.
- Final demo: 30-second video or 7 slides max.
- Small team, 48 hours: **simplicity beats completeness**. No over-engineering.
- Phase 1 must contain **infrastructure, scaffolding and data tooling only**. Product logic (RAG answers, ranking, comparison, dashboard screens) is written during the hackathon.

---

## 2. Tech stack (fixed — do not substitute)

| Layer | Choice |
|---|---|
| Frontend | Next.js (App Router) + TypeScript (strict) + Tailwind CSS, package manager **pnpm** |
| Charts | Recharts |
| 3D | React Three Fiber + @react-three/drei |
| Backend API | Python 3.11+ + FastAPI + Pydantic v2 |
| Python tooling | `uv` for env and dependencies, `ruff` for lint/format |
| Database | PostgreSQL 16 + **pgvector**, via Docker Compose |
| ORM / migrations | SQLAlchemy 2.x + Alembic |
| PDF extraction | PyMuPDF |
| ML (bonus) | pandas + scikit-learn |
| Frontend ↔ API types | `openapi-typescript` generated from FastAPI's OpenAPI schema |

**Visual design:** do NOT choose colors, fonts or a visual style. The design will come from Figma later. Use neutral Tailwind defaults and a minimal layout so screens are easy to restyle.

---

## 3. Repository structure

```
hestia/
├── README.md
├── PROJECT_SPEC.md            (this file)
├── docker-compose.yml         PostgreSQL 16 + pgvector
├── Makefile                   common commands (see §8)
├── .env.example
├── .gitignore
├── .github/workflows/ci.yml   lint + type-check + build
├── data/
│   ├── README.md              how to obtain each dataset
│   ├── ntrs/                  pdf/, text/, catalog.csv        (gitignored except README)
│   ├── psi/                   one folder per investigation   (gitignored except README)
│   └── flex/flex_table_ix.csv (committed: small, hand-made)
├── backend/
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/               migrations
│   ├── app/                   FastAPI application
│   │   ├── main.py
│   │   ├── config.py          settings from env (pydantic-settings)
│   │   ├── db.py              engine, session
│   │   ├── models.py          SQLAlchemy models (§4)
│   │   ├── schemas.py         Pydantic schemas (§5)
│   │   ├── routers/           health, experiments, compare, ranking, ask, predict
│   │   └── services/
│   │       ├── llm.py         provider-agnostic LLM + embeddings interface (§6)
│   │       └── retrieval.py   stub
│   ├── pipeline/              data tooling, runnable as CLI modules
│   │   ├── fetch_ntrs.py
│   │   ├── extract_text.py
│   │   ├── chunk.py           stub with interface
│   │   ├── embed.py           stub with interface
│   │   ├── ingest.py          stub with interface
│   │   └── queries.txt        NTRS search queries (§7)
│   └── tests/
└── web/
    ├── package.json
    ├── src/app/               one route per screen (§5.2)
    ├── src/components/        layout, nav, placeholders
    ├── src/lib/api.ts         typed API client
    └── src/lib/api-types.ts   generated from OpenAPI
```

---

## 4. Database schema (SQLAlchemy + Alembic, first migration)

Enable the `vector` extension in the first migration.

- **documents** — `id`, `ntrs_id` (unique), `title`, `authors` (text[]), `year`, `url`, `pdf_path`, `text_path`, `created_at`
- **chunks** — `id`, `document_id` (FK), `page` (int), `chunk_index`, `content` (text), `embedding` (`vector(EMBEDDING_DIM)`), `token_count`
  - HNSW or IVFFlat index on `embedding` (cosine)
- **experiments** — `id`, `code` (e.g. BASS, SAFFIRE, SAME, FLEX, ACME), `name`, `platform` (ISS, drop tower, Cygnus…), `description`, `objectives`, `psi_doi`
- **test_runs** — `id`, `experiment_id` (FK), `run_label`, `fuel`, `oxygen_percent`, `pressure_kpa`, `flow_velocity_cm_s`, `gravity` (enum: `microgravity`, `lunar`, `martian`, `earth`), `initial_diameter_mm`, `outcome` (enum: `spread`, `extinction`, `disruption`, `complete_burn`, `unknown`), `burn_rate_k`, `extra` (jsonb)
- **findings** — `id`, `experiment_id` (FK, nullable), `statement`, `relevance_moon` (float 0–1), `relevance_mars` (float 0–1), `confidence` (float 0–1)
- **finding_sources** — `finding_id` (FK), `document_id` (FK), `page`

`EMBEDDING_DIM` comes from env (default `1536`) because it depends on the embedding provider.

---

## 5. API and frontend skeleton

### 5.1 FastAPI routes (return typed **mock data** in Phase 1)
| Method | Route | Purpose |
|---|---|---|
| GET | `/health` | `{ status: "ok", db: true/false }` — real DB check |
| GET | `/experiments` | list with filters (`fuel`, `gravity`, `outcome`, `o2_min`, `o2_max`) |
| GET | `/experiments/{code}` | detail + test runs + findings + sources |
| GET | `/compare?codes=A,B,C` | side-by-side comparison |
| GET | `/ranking?target=moon\|mars` | findings ranked by relevance |
| POST | `/ask` | body `{ question }` → `{ answer, citations: [{ntrs_id, title, page, url}], insufficient_data: bool }` |
| POST | `/predict` | body `{ fuel, oxygen_percent, pressure_kpa, initial_diameter_mm }` → `{ burn_rate_k, extinction_probability }` |

- CORS enabled for the web dev origin.
- Pydantic schemas for every request/response so the OpenAPI schema is complete.

### 5.2 Next.js routes (placeholder pages, neutral styling)
| Route | Screen |
|---|---|
| `/` | Overview |
| `/experiments` | Experiment Explorer |
| `/experiments/[code]` | Experiment Detail |
| `/compare` | Compare |
| `/relevance` | Moon & Mars Relevance |
| `/assistant` | AI Assistant |
| `/simulator` | 3D Droplet Flame Simulator |

- Persistent sidebar navigation across all screens, with the product name "Hestia" as a text placeholder (no logo yet).
- Each page fetches its mock data from the API through `src/lib/api.ts` and renders it raw (simple list / JSON) — enough to prove the wiring works.
- `/simulator`: a minimal React Three Fiber canvas with a sphere and orbit controls, to prove 3D works. No flame logic yet.
- `pnpm gen:types` regenerates `api-types.ts` from `http://localhost:8000/openapi.json`.

---

## 6. LLM provider abstraction (`backend/app/services/llm.py`)

The provider is not decided yet. Implement a small interface:

```python
class LLMProvider(Protocol):
    def complete(self, system: str, messages: list[dict], json_schema: dict | None = None) -> str: ...
    def embed(self, texts: list[str]) -> list[list[float]]: ...
```

- Select the implementation with env `LLM_PROVIDER` (`openai`, `gemini`, `anthropic`, `mock`).
- Implement `mock` fully (deterministic fake embeddings of size `EMBEDDING_DIM`, canned answers) so everything runs with no API key.
- Implement the real providers as thin wrappers; they are only used when their key is set.

---

## 7. Data tooling (implement fully — this is data preparation, not product logic)

### `pipeline/fetch_ntrs.py`
- Read queries from `queries.txt` (one per line). Seed it with:
  ```
  microgravity flame spread spacecraft fire safety
  Saffire spacecraft fire experiment
  BASS burning and suppression of solids
  FLEX flame extinguishment droplet combustion
  ACME advanced combustion microgravity
  SAME smoke aerosol measurement experiment
  NASA-STD-6001 flammability microgravity
  ```
- Call the NTRS search API, collect results, deduplicate by id.
- Write `data/ntrs/catalog.csv` (id, title, authors, year, url, pdf_url).
- Download available PDFs to `data/ntrs/pdf/<id>.pdf`. Read the PDF link from the `downloads` field of each search result (verify the real response shape against the API docs before coding; links look like `/api/citations/<id>/downloads/<file>.pdf`).
- Options: `--max-per-query` (default 15), `--max-total` (default 40), polite delay between requests, retries with backoff, skip files already downloaded, clear logging.

### `pipeline/extract_text.py`
- Extract text page by page with PyMuPDF to `data/ntrs/text/<id>.jsonl` (one line per page: `{page, text}`).
- Flag documents with almost no extractable text (scanned PDFs) in a report `data/ntrs/extraction_report.csv` so the team can exclude them.

### `pipeline/chunk.py`, `embed.py`, `ingest.py`
- Define clean function signatures, docstrings and CLI entry points, with `TODO` bodies.
- `ingest.py --mock` must still insert a few fake documents/chunks/experiments using the mock provider, so the API can read real rows from the DB.

### `data/README.md`
Explain how to obtain each dataset: NTRS (script), PSI (manual download steps, which files to keep: metadata JSON and experimental tables, not raw video), FLEX (manual transcription of Table IX into `flex_table_ix.csv`, with the expected columns: `test_id, fuel, pressure_atm, o2_mole_fraction, co2_mole_fraction, n2_mole_fraction, initial_diameter_mm, outcome, burn_rate_k_mm2_s`).

Create `data/flex/flex_table_ix.csv` with the header only.

---

## 8. Developer experience

`Makefile` targets:
| Target | Action |
|---|---|
| `make up` / `make down` | start / stop Postgres |
| `make migrate` | run Alembic migrations |
| `make api` | run FastAPI with reload on :8000 |
| `make web` | run Next.js on :3000 |
| `make seed` | `ingest.py --mock` |
| `make fetch` | fetch NTRS catalog + PDFs |
| `make extract` | extract text from PDFs |
| `make lint` | ruff + eslint + tsc |
| `make types` | regenerate frontend API types |

- `.env.example`: `DATABASE_URL`, `LLM_PROVIDER=mock`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `EMBEDDING_DIM=1536`, `NEXT_PUBLIC_API_URL=http://localhost:8000`.
- `.gitignore`: env files, venvs, `node_modules`, `.next`, `data/ntrs/*` and `data/psi/*` (keep their READMEs), PDFs.
- CI (`ci.yml`): ruff, Python tests, eslint, `tsc --noEmit`, `next build`.
- README: title "Hestia", tagline, project summary, architecture diagram (ASCII), quick start in 5 commands, team roles placeholder, data sources with links, license note (NASA data public domain / CC0).

---

## 9. Conventions

- Code, comments, commits and docs in English.
- Branches: `main` (protected), `feat/<name>`, one per person; merge at each milestone.
- Conventional commits (`feat:`, `fix:`, `chore:`, `docs:`).
- Never commit secrets, PDFs or large data files.
- Keep functions small and typed; no premature abstractions beyond §6.

---

## 10. Acceptance checklist (Phase 1 is done when all pass)

- [ ] `make up && make migrate` creates all tables with the `vector` extension enabled.
- [ ] `make seed` inserts mock rows; `GET /health` returns `db: true`.
- [ ] Every route in §5.1 returns valid typed responses and appears in `/docs`.
- [ ] `make web` shows all 7 pages, navigation works, each page displays data from the API.
- [ ] `/simulator` renders a 3D sphere with orbit controls.
- [ ] `make fetch` downloads at least 20 NTRS PDFs and writes `catalog.csv`.
- [ ] `make extract` produces per-page text and the extraction report.
- [ ] The whole stack runs with `LLM_PROVIDER=mock` and no API key.
- [ ] `make lint` and CI pass.
- [ ] README quick start works on a fresh clone.

When done, print a short summary: what was built, how to run it, and any open question or deviation from this spec.
