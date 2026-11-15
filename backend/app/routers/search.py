"""Global search (the ⌘K palette): experiments, findings, NASA passages and FLEX tests.

Plain Postgres (ILIKE and full-text search), no embeddings: instant, and it works even when
the LLM provider is out of quota.
"""

import re

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.db import get_session
from app.models import Chunk, Document, Experiment, Finding, FindingSource, TestRun
from app.schemas import (
    SearchDocument,
    SearchExperiment,
    SearchFinding,
    SearchResponse,
    SearchTest,
)

router = APIRouter(tags=["search"])

WORD = re.compile(r"[^\W_][\w\-]*")
RUN_LABEL = re.compile(r"\b([a-z]+)[\s-]?(\d{1,3})\b", re.I)
PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s*%")
FUELS = {"methanol": "methanol", "heptane": "n-heptane", "n-heptane": "n-heptane"}


def prefix_tsquery(q: str) -> str | None:
    """AND of the words typed, the last one as a prefix (results update while typing)."""
    words = [w.lower().replace("-", "") for w in WORD.findall(q)]
    words = [w for w in words if w.isalnum()]
    if not words:
        return None
    return " & ".join([*words[:-1], f"{words[-1]}:*"])


def _experiments(session: Session, q: str) -> list[SearchExperiment]:
    like = f"%{q}%"
    rows = session.scalars(
        select(Experiment)
        .where(
            sa.or_(
                Experiment.code.ilike(like),
                Experiment.name.ilike(like),
                Experiment.fuels.ilike(like),
                Experiment.platform.ilike(like),
            )
        )
        .order_by(Experiment.code)
        .limit(5)
    ).all()
    return [
        SearchExperiment(code=e.code, name=e.name, platform=e.platform, fuels=e.fuels) for e in rows
    ]


def _findings(session: Session, tsq: str) -> list[SearchFinding]:
    query = func.to_tsquery("english", tsq)
    tsv = func.to_tsvector("english", Finding.statement)
    rows = session.scalars(
        select(Finding)
        .options(
            selectinload(Finding.experiment),
            selectinload(Finding.sources).selectinload(FindingSource.document),
        )
        .where(tsv.op("@@")(query))
        .order_by(func.ts_rank_cd(tsv, query).desc())
        .limit(4)
    ).all()
    out = []
    for f in rows:
        src = min(f.sources, key=lambda s: (s.document.external_id, s.page), default=None)
        out.append(
            SearchFinding(
                experiment_code=f.experiment.code if f.experiment else None,
                statement=f.statement,
                url=src.document.page_url(src.page) if src else None,
                source_label=f"{src.document.external_id}, p.{src.page}" if src else None,
            )
        )
    return out


def _documents(session: Session, tsq: str) -> list[SearchDocument]:
    query = func.to_tsquery("english", tsq)
    tsv = Chunk.content_tsv  # stored and GIN-indexed (migration 0005)
    rank = func.ts_rank_cd(tsv, query)
    # Best-matching passage per document, then the best documents.
    best = (
        select(
            Chunk.id,
            Chunk.document_id,
            rank.label("rank"),
            func.row_number()
            .over(partition_by=Chunk.document_id, order_by=rank.desc())
            .label("rn"),
        )
        .where(tsv.op("@@")(query))
        .subquery()
    )
    snippet = func.ts_headline(
        "english",
        Chunk.content,
        query,
        "StartSel=<mark>, StopSel=</mark>, MaxWords=28, MinWords=12, MaxFragments=1",
    )
    rows = session.execute(
        select(Chunk, Document, snippet.label("snippet"))
        .join(best, best.c.id == Chunk.id)
        .join(Document, Document.id == Chunk.document_id)
        .where(best.c.rn == 1)
        .order_by(best.c.rank.desc())
        .limit(6)
    ).all()
    return [
        SearchDocument(
            source_type=d.source_type,
            external_id=d.external_id,
            title=d.title,
            page=c.page,
            snippet=" ".join(s.split()),
            url=d.page_url(c.page),
        )
        for c, d, s in rows
    ]


def _tests(session: Session, q: str) -> list[SearchTest]:
    """FLEX-086 style labels, or a fuel plus an oxygen level (e.g. 'methanol 12%')."""
    stmt = select(TestRun, Experiment.code).join(Experiment, Experiment.id == TestRun.experiment_id)
    label = RUN_LABEL.search(q)
    pct = PERCENT.search(q)
    fuel = next((FUELS[w] for w in WORD.findall(q.lower()) if w in FUELS), None)
    if label and label.group(1).lower() in {"flex", "saffire"}:
        num = int(label.group(2))
        stmt = stmt.where(TestRun.run_label.ilike(f"%{label.group(1)}%{num:03d}%"))
    elif fuel or pct:
        if fuel:
            stmt = stmt.where(TestRun.fuel == fuel)
        if pct:
            o2 = float(pct.group(1))
            stmt = stmt.where(TestRun.oxygen_percent.between(o2 - 0.5, o2 + 0.5))
    else:
        return []
    rows = session.execute(stmt.order_by(TestRun.run_label).limit(5)).all()
    return [
        SearchTest(
            run_label=t.run_label or "",
            experiment_code=code,
            fuel=t.fuel,
            oxygen_percent=t.oxygen_percent,
            pressure_kpa=t.pressure_kpa,
            initial_diameter_mm=t.initial_diameter_mm,
            co2_percent=round(float((t.extra or {}).get("co2_mole_fraction") or 0.0) * 100, 1),
            outcome=str(t.outcome),
        )
        for t, code in rows
    ]


@router.get("/search", response_model=SearchResponse)
def search(
    q: str = Query(..., min_length=1, max_length=200, description="What the user typed"),
    session: Session = Depends(get_session),
) -> SearchResponse:
    """Grouped matches for the search palette. Each group is empty rather than failing."""
    q = q.strip()
    out = SearchResponse(query=q)
    if len(q) < 2:
        return out
    tsq = prefix_tsquery(q)
    try:
        out.experiments = _experiments(session, q)
        out.tests = _tests(session, q)
        if tsq:
            out.findings = _findings(session, tsq)
            out.documents = _documents(session, tsq)
    except SQLAlchemyError:
        session.rollback()
    return out
