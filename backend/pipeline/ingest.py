"""Load documents (NTRS + PSI), chunks, experiments and findings into PostgreSQL.

Usage (from backend/):
    uv run python -m pipeline.ingest                    # everything
    uv run python -m pipeline.ingest --only ntrs   # ntrs | psi | documents | experiments | findings
    uv run python -m pipeline.ingest --only psi --force # re-compute embeddings (nothing is deleted)
    uv run python -m pipeline.ingest --status           # what is indexed, with which embeddings
    uv run python -m pipeline.ingest --mock             # placeholder rows only (no data needed)

Idempotent and resumable: chunks whose text and embedding setup are current are skipped, each
embedding batch is committed before the next, so re-running after an interruption continues
where it stopped. `--force` re-embeds in place; it never deletes documents. Stale chunks of a
re-ingested document are pruned unless `--no-prune`. Findings are upserted by statement and
only removed with `--prune-findings`.
"""

import argparse
import csv
import json
import logging
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import mock_data
from app.config import DATA_DIR, get_settings
from app.db import SessionLocal
from app.models import (
    SOURCE_NTRS,
    Chunk,
    Document,
    Experiment,
    Finding,
    FindingSource,
    Gravity,
    Outcome,
    TestRun,
)
from app.services.llm import LLMProvider, MockProvider, embedding_id, get_embedder
from pipeline.chunk import chunk_file, context_prefix
from pipeline.psi import build_documents, read_psi_chunks
from pipeline.psi_runs import bass2_runs, bass_runs, saffire_runs
from pipeline.sync import (
    ChunkSpec,
    check_db_dimension,
    guard_against_mock_overwrite,
    new_counts,
    sync_document_chunks,
    text_hash,
)

PSI_CHUNKS_PATH = DATA_DIR / "psi_corpus" / "out" / "chunks.jsonl"

# Reports known to have unusable extracted text. They are never indexed automatically.
# Add ids to data/ntrs/excluded_ids.txt (one per line) without touching the code.
EXCLUDED_NTRS_IDS = {"20210015913"}

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


def excluded_ntrs_ids() -> set[str]:
    ids = set(EXCLUDED_NTRS_IDS)
    extra = DATA_DIR / "ntrs" / "excluded_ids.txt"
    if extra.exists():
        ids |= {
            line.split("#")[0].strip()
            for line in extra.read_text(encoding="utf-8").splitlines()
            if line.split("#")[0].strip()
        }
    return ids


def _upsert_document(session: Session, source_type: str, external_id: str) -> Document:
    doc = session.scalar(
        select(Document).where(
            Document.source_type == source_type, Document.external_id == external_id
        )
    )
    if doc is None:
        doc = Document(source_type=source_type, external_id=external_id, title="")
        session.add(doc)
    return doc


def ingest_ntrs(
    session: Session,
    provider: LLMProvider,
    force: bool = False,
    pause_s: float = 0.0,
    batch_size: int = 50,
    prune: bool = True,
) -> dict[str, int]:
    """Insert data/ntrs/catalog.csv + page-aware chunks (embedded with a title/year/page header).

    Upserts by (source_type="ntrs", external_id=ntrs_id). Chunks never cross a page.
    """
    catalog_path = DATA_DIR / "ntrs" / "catalog.csv"
    text_dir = DATA_DIR / "ntrs" / "text"
    if not catalog_path.exists():
        raise SystemExit("data/ntrs/catalog.csv not found. Run `make fetch extract` first.")
    flagged, excluded = _flagged_ids(), excluded_ntrs_ids()
    model_id = embedding_id()
    counts = new_counts() | {"documents": 0, "skipped": 0}

    with catalog_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        ntrs_id = row["id"]
        text_path = text_dir / f"{ntrs_id}.jsonl"
        if ntrs_id in excluded:
            log.warning(
                "%s excluded: text extraction insufficient (see EXCLUDED_NTRS_IDS)", ntrs_id
            )
            counts["skipped"] += 1
            continue
        if ntrs_id in flagged or not text_path.exists():
            counts["skipped"] += 1
            continue

        doc = _upsert_document(session, SOURCE_NTRS, ntrs_id)
        doc.ntrs_id = ntrs_id
        doc.title = row["title"]
        doc.authors = [a.strip() for a in row["authors"].split(";") if a.strip()]
        doc.year = int(row["year"]) if row.get("year") else None
        doc.url = row["url"]
        doc.pdf_url = row.get("pdf_url") or None
        doc.pdf_path = f"data/ntrs/pdf/{ntrs_id}.pdf"
        doc.text_path = f"data/ntrs/text/{ntrs_id}.jsonl"
        session.flush()

        specs = [
            ChunkSpec(
                chunk_key=f"p{c.page}#{c.chunk_index}",
                chunk_index=c.chunk_index,
                content=c.content,
                embed_text=f"{context_prefix(doc.title, doc.year, c.page)}\n{c.content}",
                page=c.page,
                token_count=c.token_count,
                meta={"content_sha256": text_hash(c.content)},
            )
            for c in chunk_file(text_path)
        ]
        res = sync_document_chunks(
            session, doc, specs, provider, model_id,
            force=force, prune=prune, batch_size=batch_size, pause_s=pause_s,
        )  # fmt: skip
        for k, v in res.items():
            counts[k] += v
        counts["documents"] += 1
        log.info("%s: %s", ntrs_id, res)
    return counts


def ingest_documents(
    session: Session, provider: LLMProvider, force: bool = False, pause_s: float = 0.0
) -> dict[str, int]:
    """Backward-compatible name for `ingest_ntrs`."""
    return ingest_ntrs(session, provider, force, pause_s)


def ingest_psi(
    session: Session,
    provider: LLMProvider,
    path: Path = PSI_CHUNKS_PATH,
    force: bool = False,
    pause_s: float = 0.0,
    batch_size: int = 50,
    prune: bool = True,
    strict: bool = False,
) -> dict[str, int]:
    """Index the prepared PSI corpus chunks (as they are) with their metadata."""
    if not path.exists():
        raise SystemExit(
            f"{path} not found. Rebuild it: "
            "python data/psi_corpus/scripts/build_corpus.py --max-chars 1800"
        )
    records, errors = read_psi_chunks(path)
    for err in errors:
        log.error("PSI chunks: %s", err)
    if errors and strict:
        raise SystemExit(f"{len(errors)} invalid PSI chunk lines (--strict)")
    model_id = embedding_id()
    counts = new_counts() | {"documents": 0, "invalid_lines": len(errors)}
    for pdoc in build_documents(records):
        doc = _upsert_document(session, pdoc.source_type, pdoc.external_id)
        doc.title, doc.url, doc.doi, doc.meta = pdoc.title, pdoc.url, pdoc.doi, pdoc.meta
        session.flush()
        res = sync_document_chunks(
            session, doc, pdoc.chunks, provider, model_id,
            force=force, prune=prune, batch_size=batch_size, pause_s=pause_s,
        )  # fmt: skip
        for k, v in res.items():
            counts[k] += v
        counts["documents"] += 1
        log.info("%s: %s", pdoc.external_id, res)
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
    test runs (FLEX from data/flex/flex_table_ix.csv; BASS, BASS-II and Saffire I-III from
    the cleaned PSI tables in data/bass/ and data/saffire/, see pipeline/psi_runs.py)."""
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
        runs = {
            "FLEX": flex_runs,
            "BASS": lambda: bass_runs() + bass2_runs(),
            "SAFFIRE": saffire_runs,
        }.get(e["code"], list)()
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


def ingest_findings(session: Session, prune: bool = False) -> dict[str, int]:
    """Upsert data/findings.json by statement. Each source must reference an ingested NTRS
    document; unknown sources are dropped with a warning. Findings missing from the file are
    kept unless `prune` (then only real ones are removed, never `[MOCK]` rows' owners)."""
    data = json.loads((DATA_DIR / "findings.json").read_text(encoding="utf-8"))
    exps = {e.code: e.id for e in session.scalars(select(Experiment))}
    docs = {
        d.external_id: d.id
        for d in session.scalars(select(Document).where(Document.source_type == SOURCE_NTRS))
    }
    existing = {f.statement: f for f in session.scalars(select(Finding))}

    counts = {"findings": 0, "sources": 0, "pruned": 0}
    for item in data:
        finding = existing.get(item["statement"]) or Finding(statement=item["statement"])
        finding.experiment_id = exps.get(item.get("experiment_code") or "")
        finding.relevance_moon = item["relevance_moon"]
        finding.relevance_mars = item["relevance_mars"]
        finding.confidence = item["confidence"]
        session.add(finding)
        session.flush()
        session.execute(delete(FindingSource).where(FindingSource.finding_id == finding.id))
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
    if prune:
        keep = {item["statement"] for item in data}
        for statement, f in existing.items():
            if statement not in keep and not statement.startswith("[MOCK]"):
                session.delete(f)
                counts["pruned"] += 1
    elif stale := [st for st in existing if st not in {i["statement"] for i in data}]:
        log.warning("%d findings in the database are not in findings.json (kept)", len(stale))
    session.commit()
    return counts


def ingest_mock(session: Session) -> dict[str, int]:
    """Insert placeholder documents, chunks (mock embeddings), experiments, runs, findings."""
    provider = MockProvider(get_settings().embedding_dim)
    counts = {"documents": 0, "chunks": 0, "experiments": 0, "test_runs": 0, "findings": 0}

    docs: dict[str, Document] = {}
    for d in mock_data.MOCK_DOCUMENTS:
        doc = session.scalar(
            select(Document).where(
                Document.source_type == SOURCE_NTRS, Document.external_id == d["ntrs_id"]
            )
        )
        if doc is None:
            doc = Document(
                source_type=SOURCE_NTRS,
                external_id=d["ntrs_id"],
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
                        chunk_key=f"p{i + 1}#{i}",
                        content=text,
                        content_hash=text_hash(text),
                        embedding=vec,
                        embedding_model=embedding_id(),
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
        "--only",
        choices=["ntrs", "psi", "documents", "experiments", "findings"],
        help="run a single step (documents = ntrs + psi)",
    )
    parser.add_argument(
        "--force", action="store_true", help="re-embed chunks in place (no deletion)"
    )
    parser.add_argument(
        "--no-prune", action="store_true", help="keep stale chunks of re-ingested documents"
    )
    parser.add_argument(
        "--prune-findings", action="store_true", help="delete findings absent from findings.json"
    )
    parser.add_argument("--status", action="store_true", help="print the indexing state and exit")
    parser.add_argument("--strict", action="store_true", help="fail on invalid PSI chunk lines")
    parser.add_argument("--psi-chunks", type=Path, default=PSI_CHUNKS_PATH)
    parser.add_argument("--batch-size", type=int, default=50, help="texts per embedding request")
    parser.add_argument(
        "--pause", type=float, default=0.0, help="seconds between batches (free tiers)"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.status:
        from pipeline.status import print_status

        print_status()
        return
    with SessionLocal() as session:
        if args.mock:
            log.info("Inserted mock rows: %s", ingest_mock(session))
            return
        provider, prune = get_embedder(), not args.no_prune
        wants_docs = args.only in (None, "documents", "ntrs", "psi")
        if wants_docs:
            check_db_dimension(session)
            guard_against_mock_overwrite(session, embedding_id())
            log.info("Embedding setup: %s", embedding_id())
        remove_mock_rows(session)
        if args.only in (None, "documents", "ntrs"):
            counts = ingest_ntrs(session, provider, args.force, args.pause, args.batch_size, prune)
            log.info("NTRS: %s", counts)
        if args.only in (None, "documents", "psi"):
            counts = ingest_psi(
                session, provider, args.psi_chunks, args.force, args.pause,
                args.batch_size, prune, args.strict,
            )  # fmt: skip
            log.info("PSI: %s", counts)
        if args.only in (None, "experiments"):
            log.info("Experiments: %s", ingest_experiments(session))
        if args.only in (None, "findings"):
            log.info("Findings: %s", ingest_findings(session, args.prune_findings))


if __name__ == "__main__":
    main()
