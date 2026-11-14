"""Load documents, chunks, experiments and findings into PostgreSQL.

Usage (from backend/):
    uv run python -m pipeline.ingest                   # documents + experiments + findings
    uv run python -m pipeline.ingest --only documents  # one step (documents|experiments|findings)
    uv run python -m pipeline.ingest --force           # re-chunk and re-embed every document
    uv run python -m pipeline.ingest --mock            # placeholder rows only (no data needed)

Real ingestion removes `--mock` rows first. Embeddings use LLM_PROVIDER: with `mock`
they are fake vectors, so run with a real provider (e.g. gemini) for meaningful search.
`--mock` is idempotent: rows that already exist (same ntrs_id / experiment code) are skipped.
"""

import argparse
import csv
import json
import logging

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import mock_data
from app.config import DATA_DIR, get_settings
from app.db import SessionLocal
from app.models import (
    Chunk,
    Document,
    Experiment,
    Finding,
    FindingSource,
    Gravity,
    Outcome,
    TestRun,
)
from app.services.llm import LLMProvider, MockProvider, get_provider
from pipeline.chunk import chunk_file
from pipeline.embed import embed_chunks

log = logging.getLogger("ingest")


def remove_mock_rows(session: Session) -> None:
    """Delete placeholder rows inserted by `--mock` so they never mix with real data."""
    session.execute(delete(Document).where(Document.ntrs_id.like("MOCK-%")))
    session.execute(delete(Finding).where(Finding.statement.like("[MOCK]%")))
    session.execute(delete(TestRun).where(TestRun.run_label.like("%-M_")))
    session.commit()


def _flagged_ids() -> set[str]:
    """Documents marked `low_text` by extract_text (scanned PDFs) are not indexed."""
    report = DATA_DIR / "ntrs" / "extraction_report.csv"
    if not report.exists():
        return set()
    with report.open(encoding="utf-8") as f:
        return {r["ntrs_id"] for r in csv.DictReader(f) if r["status"] != "ok"}


def ingest_documents(
    session: Session, provider: LLMProvider, force: bool = False, pause_s: float = 0.0
) -> dict[str, int]:
    """Insert data/ntrs/catalog.csv + chunked, embedded text into `documents`/`chunks`.

    Upserts by ntrs_id. Documents that already have chunks are skipped unless `force`.
    Commits after each document, so an interrupted run can simply be restarted.
    """
    catalog_path = DATA_DIR / "ntrs" / "catalog.csv"
    text_dir = DATA_DIR / "ntrs" / "text"
    if not catalog_path.exists():
        raise SystemExit("data/ntrs/catalog.csv not found. Run `make fetch` first.")
    flagged = _flagged_ids()
    dim = get_settings().embedding_dim
    counts = {"documents": 0, "chunks": 0, "skipped": 0}

    with catalog_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        ntrs_id = row["id"]
        text_path = text_dir / f"{ntrs_id}.jsonl"
        if ntrs_id in flagged or not text_path.exists():
            counts["skipped"] += 1
            continue

        doc = session.scalar(select(Document).where(Document.ntrs_id == ntrs_id))
        if doc is None:
            doc = Document(ntrs_id=ntrs_id)
            session.add(doc)
        doc.title = row["title"]
        doc.authors = [a.strip() for a in row["authors"].split(";") if a.strip()]
        doc.year = int(row["year"]) if row.get("year") else None
        doc.url = row["url"]
        doc.pdf_url = row.get("pdf_url") or None
        doc.pdf_path = f"data/ntrs/pdf/{ntrs_id}.pdf"
        doc.text_path = f"data/ntrs/text/{ntrs_id}.jsonl"
        session.flush()

        has_chunks = session.scalar(select(Chunk.id).where(Chunk.document_id == doc.id).limit(1))
        if has_chunks and not force:
            session.commit()
            continue
        session.execute(delete(Chunk).where(Chunk.document_id == doc.id))

        chunks = chunk_file(text_path)
        vectors = embed_chunks(chunks, provider, pause_s=pause_s) if chunks else []
        if vectors and len(vectors[0]) != dim:
            raise SystemExit(
                f"Embedding size {len(vectors[0])} != EMBEDDING_DIM={dim}. Fix .env or the model."
            )
        for c, vec in zip(chunks, vectors, strict=True):
            session.add(
                Chunk(
                    document_id=doc.id,
                    page=c.page,
                    chunk_index=c.chunk_index,
                    content=c.content,
                    embedding=vec,
                    token_count=c.token_count,
                )
            )
        session.commit()
        counts["documents"] += 1
        counts["chunks"] += len(chunks)
        log.info("%s: %d chunks", ntrs_id, len(chunks))
    return counts


def _float(v: str | None) -> float | None:
    return float(v) if v not in ("", None) else None


_FLEX_EXTRA = (
    "co2_mole_fraction",
    "n2_mole_fraction",
    "he_mole_fraction",
    "extinction_diameter_mm",
    "burn_time_s",
)


def flex_runs() -> list[dict]:
    """FLEX Table IX rows (data/flex/flex_table_ix.csv) as `test_runs` fields."""
    path = DATA_DIR / "flex" / "flex_table_ix.csv"
    if not path.exists():
        return []
    runs = []
    with path.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            p_atm = _float(r["pressure_atm"])
            o2 = _float(r["o2_mole_fraction"])
            extra: dict = {k: _float(r[k]) for k in _FLEX_EXTRA if r.get(k) not in ("", None)}
            extra["test_date"] = r.get("test_date")
            extra["source"] = f"NTRS 20150023456, Table IX, p.{r['source_page']}"
            runs.append(
                {
                    "run_label": r["test_id"],
                    "fuel": r["fuel"],
                    "oxygen_percent": round(o2 * 100, 2) if o2 is not None else None,
                    "pressure_kpa": round(p_atm * 101.325, 2) if p_atm is not None else None,
                    "flow_velocity_cm_s": 0.0,
                    "gravity": Gravity.microgravity,
                    "initial_diameter_mm": _float(r["initial_diameter_mm"]),
                    "outcome": Outcome(r["outcome"]),
                    "burn_rate_k": _float(r["burn_rate_k_mm2_s"]),
                    "extra": extra,
                }
            )
    return runs


def ingest_experiments(session: Session) -> dict[str, int]:
    """Upsert data/experiments.json into `experiments` and replace each experiment's
    test runs (FLEX runs come from data/flex/flex_table_ix.csv)."""
    data = json.loads((DATA_DIR / "experiments.json").read_text(encoding="utf-8"))
    counts = {"experiments": 0, "test_runs": 0}
    for e in data:
        exp = session.scalar(select(Experiment).where(Experiment.code == e["code"]))
        if exp is None:
            exp = Experiment(code=e["code"])
            session.add(exp)
        for field in ("name", "platform", "description", "objectives", "psi_doi", "years", "fuels"):
            setattr(exp, field, e.get(field))
        session.flush()

        session.execute(delete(TestRun).where(TestRun.experiment_id == exp.id))
        runs = flex_runs() if e["code"] == "FLEX" else []
        for r in e.get("runs", []):
            runs.append(
                r
                | {
                    "gravity": Gravity(r.get("gravity", "microgravity")),
                    "outcome": Outcome(r.get("outcome", "unknown")),
                }
            )
        for r in runs:
            session.add(TestRun(experiment_id=exp.id, **r))
        counts["experiments"] += 1
        counts["test_runs"] += len(runs)
    session.commit()
    return counts


def ingest_findings(session: Session) -> dict[str, int]:
    """Replace all findings with data/findings.json. Each source must reference an
    ingested document (by ntrs_id); unknown sources are dropped with a warning."""
    data = json.loads((DATA_DIR / "findings.json").read_text(encoding="utf-8"))
    exps = {e.code: e.id for e in session.scalars(select(Experiment))}
    docs = {d.ntrs_id: d.id for d in session.scalars(select(Document))}

    session.execute(delete(Finding))
    counts = {"findings": 0, "sources": 0}
    for item in data:
        finding = Finding(
            experiment_id=exps.get(item.get("experiment_code") or ""),
            statement=item["statement"],
            relevance_moon=item["relevance_moon"],
            relevance_mars=item["relevance_mars"],
            confidence=item["confidence"],
        )
        session.add(finding)
        session.flush()
        seen: set[tuple[int, int]] = set()
        for s in item["sources"]:
            doc_id = docs.get(s["ntrs_id"])
            if doc_id is None:
                log.warning("Finding source %s is not ingested; dropped", s["ntrs_id"])
                continue
            if (doc_id, s["page"]) in seen:
                continue
            seen.add((doc_id, s["page"]))
            session.add(FindingSource(finding_id=finding.id, document_id=doc_id, page=s["page"]))
            counts["sources"] += 1
        counts["findings"] += 1
    session.commit()
    return counts


def ingest_mock(session: Session) -> dict[str, int]:
    """Insert placeholder documents, chunks (mock embeddings), experiments, runs, findings."""
    provider = MockProvider(get_settings().embedding_dim)
    counts = {"documents": 0, "chunks": 0, "experiments": 0, "test_runs": 0, "findings": 0}

    docs: dict[str, Document] = {}
    for d in mock_data.MOCK_DOCUMENTS:
        doc = session.scalar(select(Document).where(Document.ntrs_id == d["ntrs_id"]))
        if doc is None:
            doc = Document(
                ntrs_id=d["ntrs_id"],
                title=d["title"],
                authors=["Mock, Author"],
                year=2020,
                url=mock_data.mock_doc_url(d["ntrs_id"]),
            )
            session.add(doc)
            session.flush()
            texts = [f"[MOCK] {d['title']} — page {p} placeholder text." for p in (1, 2, 3)]
            for i, (text, vec) in enumerate(zip(texts, provider.embed(texts), strict=True)):
                session.add(
                    Chunk(
                        document_id=doc.id,
                        page=i + 1,
                        chunk_index=i,
                        content=text,
                        embedding=vec,
                        token_count=len(text.split()),
                    )
                )
                counts["chunks"] += 1
            counts["documents"] += 1
        docs[d["ntrs_id"]] = doc

    for e in mock_data.experiments():
        if session.scalar(select(Experiment).where(Experiment.code == e.code)):
            continue
        exp = Experiment(
            code=e.code,
            name=e.name,
            platform=e.platform,
            description=e.description,
            objectives=e.objectives,
        )
        session.add(exp)
        session.flush()
        for r in e.test_runs:
            session.add(TestRun(experiment_id=exp.id, **r.model_dump()))
            counts["test_runs"] += 1
        for f in e.findings:
            finding = Finding(
                experiment_id=exp.id,
                statement=f.statement,
                relevance_moon=f.relevance_moon,
                relevance_mars=f.relevance_mars,
                confidence=f.confidence,
            )
            session.add(finding)
            session.flush()
            for s in f.sources:
                session.add(
                    FindingSource(
                        finding_id=finding.id, document_id=docs[s.ntrs_id].id, page=s.page
                    )
                )
            counts["findings"] += 1
        counts["experiments"] += 1

    session.commit()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mock", action="store_true", help="insert placeholder rows only")
    parser.add_argument(
        "--only", choices=["documents", "experiments", "findings"], help="run a single step"
    )
    parser.add_argument("--force", action="store_true", help="re-chunk and re-embed documents")
    parser.add_argument(
        "--pause", type=float, default=0.0, help="seconds between embedding batches (free tiers)"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    with SessionLocal() as session:
        if args.mock:
            log.info("Inserted mock rows: %s", ingest_mock(session))
            return
        remove_mock_rows(session)
        if args.only in (None, "documents"):
            counts = ingest_documents(session, get_provider(), args.force, args.pause)
            log.info("Documents: %s", counts)
        if args.only in (None, "experiments"):
            log.info("Experiments: %s", ingest_experiments(session))
        if args.only in (None, "findings"):
            log.info("Findings: %s", ingest_findings(session))


if __name__ == "__main__":
    main()
