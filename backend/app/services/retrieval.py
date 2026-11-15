"""Hybrid retrieval over `chunks`: pgvector cosine similarity + Postgres full-text search.

Both rankings are merged with reciprocal rank fusion (RRF). Keyword search keeps acronyms
(BASS, FLEX, PSI-159) and exact numbers findable; with the mock provider (fake embeddings)
only keyword search is used.

Relevance gate (RETRIEVAL_MIN_SCORE)
    The score of a passage is its **cosine similarity** to the question (1 - cosine distance,
    higher is better). With a real embedding provider, *every* candidate, whether it came
    from the vector search or from the keyword search, gets its real similarity and must reach
    RETRIEVAL_MIN_SCORE. Keyword hits only add candidates and influence the ranking: they can
    no longer bypass the gate. The default threshold is provisional; calibrate it with
    `make calibrate` (see docs/RAG.md).
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any

import sqlalchemy as sa
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Chunk, Document
from app.services.llm import MockProvider, check_dimension, get_embedder

log = logging.getLogger(__name__)

RRF_K = 60
CANDIDATES = 24

# metadata keys that /ask callers (and tests) may filter on
FILTERABLE_META = ("psi_id", "fuel_category", "fire_safety_tier", "section", "pillars")

_STOPWORDS_EN = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "does", "for", "from",
    "how", "in", "is", "it", "of", "on", "or", "the", "to", "what", "when", "where",
    "which", "who", "why", "with", "would", "will", "should", "could", "there", "this",
    "that", "these", "those", "about", "tell", "me", "explain", "between", "compare",
}  # fmt: skip
_STOPWORDS_FR = {
    "le", "la", "les", "un", "une", "des", "du", "de", "et", "ou", "est", "sont", "au",
    "aux", "en", "dans", "pour", "par", "sur", "avec", "que", "qui", "quoi", "quel",
    "quelle", "quels", "quelles", "comment", "pourquoi", "peut", "peuvent", "entre",
    "ce", "cette", "ces", "se", "sa", "son", "ses", "il", "elle", "ils", "elles", "dit",
    "expliquer", "explique", "comparer", "compare", "dire",
}  # fmt: skip
_STOPWORDS = _STOPWORDS_EN | _STOPWORDS_FR


@dataclass
class RetrievedChunk:
    ntrs_id: str  # external id of the source: NTRS id, "PSI-159" or a resource slug
    title: str
    page: int | None
    content: str
    url: str | None
    score: float  # cosine similarity (0 with the mock provider)
    keyword_hit: bool = False
    source_type: str = "ntrs"
    doi: str | None = None
    chunk_id: int | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def source_id(self) -> str:
        return self.ntrs_id


def keyword_query(question: str) -> str | None:
    """OR-query for to_tsquery from the question's content words, or None."""
    words = [w.lower() for w in re.findall(r"[^\W\d_][\w\-]+", question)]
    terms = sorted({w.replace("-", "") for w in words if w not in _STOPWORDS})
    terms = [t for t in terms if t.isalnum()]
    return " | ".join(terms) or None


def _conditions(source_types: list[str] | None, meta_filters: dict[str, Any] | None) -> list:
    conds: list = []
    if source_types:
        conds.append(Document.source_type.in_(source_types))
    for key, value in (meta_filters or {}).items():
        if key not in FILTERABLE_META:
            raise ValueError(f"Unsupported metadata filter: {key}")
        if key == "pillars":
            conds.append(Chunk.meta.contains({"pillars": [value]}))
        else:
            conds.append(Chunk.meta[key].as_string() == str(value))
    return conds


def _to_retrieved(chunk: Chunk, doc: Document, score: float, keyword: bool) -> RetrievedChunk:
    return RetrievedChunk(
        ntrs_id=doc.external_id,
        title=doc.title,
        page=chunk.page,
        content=chunk.content,
        url=doc.page_url(chunk.page),
        score=score,
        keyword_hit=keyword,
        source_type=doc.source_type,
        doi=doc.doi,
        chunk_id=chunk.id,
        meta=dict(chunk.meta or {}),
    )


def _similarity(distance: Any) -> float:
    return round(1 - float(distance), 4) if distance is not None else 0.0


def _vector_search(
    session: Session, vec: list[float], n: int, conds: list, model_id: str | None
) -> list[RetrievedChunk]:
    distance = Chunk.embedding.cosine_distance(vec)
    stmt = (
        select(Chunk, Document, distance.label("d"))
        .join(Document, Chunk.document_id == Document.id)
        .where(Chunk.embedding.is_not(None), *conds)
    )
    if model_id:  # never compare a query with vectors from another embedding setup
        stmt = stmt.where(Chunk.embedding_model == model_id)
    rows = session.execute(stmt.order_by(distance).limit(n)).all()
    return [_to_retrieved(c, d, _similarity(dist), False) for c, d, dist in rows]


def _keyword_search(
    session: Session,
    question: str,
    vec: list[float] | None,
    n: int,
    conds: list,
    model_id: str | None,
) -> list[RetrievedChunk]:
    q = keyword_query(question)
    if q is None:
        return []
    tsv = func.to_tsvector("english", Chunk.content)
    tsq = func.to_tsquery("english", q)
    rank = func.ts_rank_cd(tsv, tsq)
    if vec is not None:
        # similarity only against vectors from the same embedding setup, else unknown (NULL)
        distance = sa.case(
            (Chunk.embedding_model == model_id, Chunk.embedding.cosine_distance(vec)),
            else_=sa.null(),
        )
    else:
        distance = sa.null()
    rows = session.execute(
        select(Chunk, Document, distance.label("d"))
        .join(Document, Chunk.document_id == Document.id)
        .where(tsv.op("@@")(tsq), *conds)
        .order_by(rank.desc())
        .limit(n)
    ).all()
    return [_to_retrieved(c, d, _similarity(dist), True) for c, d, dist in rows]


def search(
    session: Session,
    question: str,
    k: int | None = None,
    source_types: list[str] | None = None,
    meta_filters: dict[str, Any] | None = None,
    apply_threshold: bool = True,
) -> list[RetrievedChunk]:
    """Return up to k chunks most relevant to `question`, best first.

    With a real provider, chunks whose cosine similarity is below RETRIEVAL_MIN_SCORE are
    dropped (set `apply_threshold=False` to see raw scores, e.g. for calibration). With the
    mock provider only keyword search is used and no threshold applies.
    """
    from app.services.llm import embedding_id

    s = get_settings()
    k = k or s.retrieval_k
    provider = get_embedder()
    use_vectors = not isinstance(provider, MockProvider)
    conds = _conditions(source_types, meta_filters)
    vec: list[float] | None = None
    if use_vectors:
        try:
            vec = provider.embed([question], task="query")[0]
        except Exception as exc:  # quota, network: degrade to keyword search, don't fail
            log.warning("Query embedding failed (%s); keyword search only", exc.__class__.__name__)
            use_vectors = False
    try:
        if vec is not None:
            check_dimension([vec], s.embedding_dim)
        vector_hits = _vector_search(session, vec, CANDIDATES, conds, embedding_id()) if vec else []
        keyword_hits = _keyword_search(session, question, vec, CANDIDATES, conds, embedding_id())
    except SQLAlchemyError as exc:
        log.warning("Retrieval failed: %s", exc.__class__.__name__)
        session.rollback()
        return []

    merged: dict[int | tuple, RetrievedChunk] = {}
    fused: dict[int | tuple, float] = {}
    for hits in (vector_hits, keyword_hits):
        for rank, h in enumerate(hits):
            key = h.chunk_id if h.chunk_id is not None else (h.ntrs_id, h.page, h.content[:80])
            fused[key] = fused.get(key, 0.0) + 1.0 / (RRF_K + rank + 1)
            if key in merged:
                merged[key].keyword_hit |= h.keyword_hit
                merged[key].score = max(merged[key].score, h.score)
            else:
                merged[key] = h

    ranked = sorted(merged, key=lambda key: fused[key], reverse=True)
    out: list[RetrievedChunk] = []
    per_doc: dict[tuple[str, str], int] = {}
    for key in ranked:
        c = merged[key]
        if use_vectors and apply_threshold and c.score < s.retrieval_min_score:
            continue
        doc_key = (c.source_type, c.ntrs_id)
        if per_doc.get(doc_key, 0) >= s.retrieval_max_per_doc:
            continue
        per_doc[doc_key] = per_doc.get(doc_key, 0) + 1
        out.append(c)
    return out[:k]
