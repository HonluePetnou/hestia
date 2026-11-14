"""Idempotent, resumable chunk synchronisation for one document.

For each `ChunkSpec` the (document, chunk_key) row is:
  - left alone when its content hash, embedding and embedding setup are all current;
  - otherwise (new / changed text / no vector / vector from another provider or `force`)
    embedded and written. Each batch is committed before the next is requested, so an
    interrupted run resumes from the first chunk that has no valid vector.

Rows are never deleted except stale chunks of the same document (a chunk_key that no longer
exists in the source) and only when `prune=True`. `force` re-computes vectors in place: it
deletes nothing.
"""

import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Chunk, Document
from app.services.llm import LLMProvider
from pipeline.embed import embed_batch

log = logging.getLogger("sync")


@dataclass
class ChunkSpec:
    chunk_key: str
    chunk_index: int
    content: str  # stored and shown to the LLM / user
    embed_text: str  # exactly what is embedded (content with an optional context header)
    page: int | None = None
    token_count: int | None = None
    meta: dict[str, Any] = field(default_factory=dict)


def text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def new_counts() -> dict[str, int]:
    return {"new": 0, "reembedded": 0, "unchanged": 0, "pruned": 0}


def sync_document_chunks(
    session: Session,
    doc: Document,
    specs: list[ChunkSpec],
    provider: LLMProvider,
    model_id: str,
    *,
    force: bool = False,
    prune: bool = True,
    batch_size: int = 50,
    pause_s: float = 0.0,
) -> dict[str, int]:
    keys = [s.chunk_key for s in specs]
    if len(keys) != len(set(keys)):
        raise ValueError(f"Duplicate chunk_key in {doc.external_id}")

    counts = new_counts()
    existing = {
        c.chunk_key: c for c in session.scalars(select(Chunk).where(Chunk.document_id == doc.id))
    }
    todo: list[tuple[ChunkSpec, str, Chunk | None]] = []
    for spec in specs:
        h = text_hash(spec.embed_text)
        row = existing.get(spec.chunk_key)
        current = (
            row is not None
            and not force
            and row.content_hash == h
            and row.embedding is not None
            and row.embedding_model == model_id
        )
        if current:
            row.page, row.chunk_index, row.meta = spec.page, spec.chunk_index, spec.meta
            counts["unchanged"] += 1
        else:
            todo.append((spec, h, row))

    for start in range(0, len(todo), batch_size):
        batch = todo[start : start + batch_size]
        vectors = embed_batch(provider, [s.embed_text for s, _, _ in batch])
        for (spec, h, row), vec in zip(batch, vectors, strict=True):
            if row is None:
                row = Chunk(document_id=doc.id, chunk_key=spec.chunk_key)
                session.add(row)
                counts["new"] += 1
            else:
                counts["reembedded"] += 1
            row.chunk_index, row.page = spec.chunk_index, spec.page
            row.content, row.content_hash = spec.content, h
            row.token_count, row.meta = spec.token_count, spec.meta
            row.embedding, row.embedding_model = vec, model_id
        session.commit()  # progressive save: a crash loses at most this batch
        log.info("%s: %d/%d chunks embedded", doc.external_id, start + len(batch), len(todo))
        if pause_s:
            time.sleep(pause_s)

    stale = [c for k, c in existing.items() if k not in set(keys)]
    if stale and prune:
        for c in stale:
            session.delete(c)
        counts["pruned"] = len(stale)
    elif stale:
        log.warning("%s: %d stale chunks kept (--no-prune)", doc.external_id, len(stale))
    session.commit()
    return counts


def guard_against_mock_overwrite(session: Session, model_id: str) -> None:
    """Refuse to replace real vectors with fake ones (LLM_PROVIDER=mock on a real index)."""
    if not model_id.startswith("mock:"):
        return
    real = session.scalar(
        select(Chunk.id)
        .where(Chunk.embedding_model.is_not(None), Chunk.embedding_model.not_like("mock:%"))
        .limit(1)
    )
    if real is not None:
        raise SystemExit(
            "Refusing to run with LLM_PROVIDER=mock: the index contains real embeddings that "
            "would be overwritten with fake ones. Set LLM_PROVIDER to your real provider."
        )


def check_db_dimension(session: Session) -> None:
    """The chunks.embedding column size must equal EMBEDDING_DIM."""
    dim = session.scalar(
        text(
            "SELECT atttypmod FROM pg_attribute "
            "WHERE attrelid = 'chunks'::regclass AND attname = 'embedding'"
        )
    )
    expected = get_settings().embedding_dim
    if dim != expected:
        raise SystemExit(
            f"chunks.embedding is vector({dim}) but EMBEDDING_DIM={expected}. "
            "Changing the dimension needs a migration (see docs/RAG.md, 'Changing the dimension')."
        )
