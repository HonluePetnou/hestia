"""Load documents, chunks and experiments into PostgreSQL.

Usage (from backend/):
    uv run python -m pipeline.ingest --mock   # insert placeholder rows (works today)
    uv run python -m pipeline.ingest          # real ingestion — TODO (Phase 2)

`--mock` is idempotent: rows that already exist (same ntrs_id / experiment code) are skipped.
"""

import argparse
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import mock_data
from app.config import get_settings
from app.db import SessionLocal
from app.models import Chunk, Document, Experiment, Finding, FindingSource, TestRun
from app.services.llm import MockProvider

log = logging.getLogger("ingest")


def ingest_documents(session: Session) -> None:
    """Insert data/ntrs/catalog.csv + chunked, embedded text into `documents`/`chunks`.

    TODO: read the catalog, run pipeline.chunk + pipeline.embed, upsert by ntrs_id.
    """
    raise NotImplementedError


def ingest_experiments(session: Session) -> None:
    """Insert PSI metadata + FLEX table into `experiments`/`test_runs`. TODO."""
    raise NotImplementedError


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
    parser.add_argument("--mock", action="store_true", help="insert placeholder rows")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    with SessionLocal() as session:
        if args.mock:
            counts = ingest_mock(session)
            log.info("Inserted mock rows: %s", counts)
        else:
            raise SystemExit("TODO: real ingestion is not implemented yet. Use --mock.")


if __name__ == "__main__":
    main()
