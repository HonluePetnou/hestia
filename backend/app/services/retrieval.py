"""Hybrid retrieval over `chunks`: pgvector cosine similarity + Postgres full-text search.

The two rankings are merged with reciprocal rank fusion (RRF). Keyword search keeps
acronyms (BASS, FLEX, NASA-STD-6001) and exact numbers findable, and lets the mock
provider return relevant passages without real embeddings.
"""

import logging
import re
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Chunk, Document
from app.services.llm import MockProvider, get_provider

log = logging.getLogger(__name__)

RRF_K = 60
CANDIDATES = 24

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "does", "for", "from",
    "how", "in", "is", "it", "of", "on", "or", "the", "to", "what", "when", "where",
    "which", "who", "why", "with", "would", "will", "should", "could", "there", "this",
    "that", "these", "those", "about", "tell", "me", "explain", "between", "compare",
}  # fmt: skip


@dataclass
class RetrievedChunk:
    ntrs_id: str
    title: str
    page: int
    content: str
    url: str
    score: float  # cosine similarity (0 when the chunk came from keyword search only)
    keyword_hit: bool = False


def keyword_query(question: str) -> str | None:
    """OR-query for to_tsquery from the question's content words, or None."""
    words = [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9\-]{1,}", question)]
    terms = sorted({w.replace("-", "") for w in words if w not in _STOPWORDS})
    return " | ".join(terms) or None


def _rows_to_chunks(rows, score_of) -> list[RetrievedChunk]:
    return [
        RetrievedChunk(
            ntrs_id=doc.ntrs_id,
            title=doc.title,
            page=chunk.page,
            content=chunk.content,
            url=doc.page_url(chunk.page),
            score=score_of(metric),
        )
        for chunk, doc, metric in rows
    ]


def _vector_search(session: Session, question: str, n: int) -> list[RetrievedChunk]:
    vec = get_provider().embed([question], task="query")[0]
    distance = Chunk.embedding.cosine_distance(vec)
    rows = session.execute(
        select(Chunk, Document, distance.label("d"))
        .join(Document, Chunk.document_id == Document.id)
        .where(Chunk.embedding.is_not(None))
        .order_by(distance)
        .limit(n)
    ).all()
    return _rows_to_chunks(rows, lambda d: round(1 - float(d), 4))


def _keyword_search(session: Session, question: str, n: int) -> list[RetrievedChunk]:
    q = keyword_query(question)
    if q is None:
        return []
    tsv = func.to_tsvector("english", Chunk.content)
    tsq = func.to_tsquery("english", q)
    rank = func.ts_rank_cd(tsv, tsq)
    rows = session.execute(
        select(Chunk, Document, rank.label("r"))
        .join(Document, Chunk.document_id == Document.id)
        .where(tsv.op("@@")(tsq))
        .order_by(rank.desc())
        .limit(n)
    ).all()
    hits = _rows_to_chunks(rows, lambda _: 0.0)
    for h in hits:
        h.keyword_hit = True
    return hits


def search(session: Session, question: str, k: int | None = None) -> list[RetrievedChunk]:
    """Return up to k chunks most relevant to `question`, best first.

    Chunks below RETRIEVAL_MIN_SCORE (cosine) are dropped unless keyword search also
    found them. With the mock provider only keyword search is used.
    """
    s = get_settings()
    k = k or s.retrieval_k
    use_vectors = not isinstance(get_provider(), MockProvider)
    try:
        vector_hits = _vector_search(session, question, CANDIDATES) if use_vectors else []
        keyword_hits = _keyword_search(session, question, CANDIDATES)
    except SQLAlchemyError as exc:
        log.warning("Retrieval failed: %s", exc.__class__.__name__)
        session.rollback()
        return []

    merged: dict[tuple[str, int, str], RetrievedChunk] = {}
    fused: dict[tuple[str, int, str], float] = {}
    for hits in (vector_hits, keyword_hits):
        for rank, h in enumerate(hits):
            key = (h.ntrs_id, h.page, h.content[:80])
            fused[key] = fused.get(key, 0.0) + 1.0 / (RRF_K + rank + 1)
            if key in merged:
                merged[key].keyword_hit |= h.keyword_hit
                merged[key].score = max(merged[key].score, h.score)
            else:
                merged[key] = h

    ranked = sorted(merged, key=lambda key: fused[key], reverse=True)
    out = [
        merged[key]
        for key in ranked
        if not use_vectors or merged[key].score >= s.retrieval_min_score or merged[key].keyword_hit
    ]
    return out[:k]
