"""Indexing state: counts per source, embedding coverage, embedding setups, dimension.

uv run python -m pipeline.status      (or: make ingest-status)
"""

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.models import Chunk, Document
from app.services.llm import embedding_id


def collect_status(session: Session) -> dict:
    per_source = [
        {
            "source_type": st,
            "documents": docs,
            "chunks": chunks,
            "embedded": embedded,
            "without_page": no_page,
        }
        for st, docs, chunks, embedded, no_page in session.execute(
            select(
                Document.source_type,
                func.count(func.distinct(Document.id)),
                func.count(Chunk.id),
                func.count(Chunk.embedding),
                func.count(Chunk.id).filter(Chunk.page.is_(None)),
            )
            .join(Chunk, Chunk.document_id == Document.id, isouter=True)
            .group_by(Document.source_type)
            .order_by(Document.source_type)
        )
    ]
    models = dict(
        session.execute(
            select(Chunk.embedding_model, func.count()).group_by(Chunk.embedding_model)
        ).all()
    )
    column_dim = session.scalar(
        text(
            "SELECT atttypmod FROM pg_attribute "
            "WHERE attrelid = 'chunks'::regclass AND attname = 'embedding'"
        )
    )
    stored_dims = [
        r[0]
        for r in session.execute(
            text("SELECT DISTINCT vector_dims(embedding) FROM chunks WHERE embedding IS NOT NULL")
        )
    ]
    return {
        "configured_embedding": embedding_id(),
        "embedding_dim_setting": get_settings().embedding_dim,
        "column_dim": column_dim,
        "stored_vector_dims": stored_dims,
        "embedding_models": {str(k): v for k, v in models.items()},
        "sources": per_source,
    }


def print_status() -> None:
    with SessionLocal() as session:
        st = collect_status(session)
    print(f"Configured embeddings : {st['configured_embedding']}")
    print(f"Column vector({st['column_dim']}), EMBEDDING_DIM={st['embedding_dim_setting']}, "
          f"stored dims={st['stored_vector_dims']}")  # fmt: skip
    ok = st["column_dim"] == st["embedding_dim_setting"]
    print("Dimension check       : " + ("OK" if ok else "MISMATCH, see docs/RAG.md"))
    print("\nsource_type      docs  chunks  embedded  no_page")
    for r in st["sources"]:
        cols = (r["documents"], r["chunks"], r["embedded"], r["without_page"])
        print(f"{r['source_type']:<15} {cols[0]:>5} {cols[1]:>7} {cols[2]:>9} {cols[3]:>8}")
    print("\nEmbedding setups in the index (chunks):")
    for model, n in st["embedding_models"].items():
        mark = (
            ""
            if model == st["configured_embedding"]
            else "   <- differs from current config: run `make ingest`"
        )
        print(f"  {model:<40} {n:>6}{mark}")


if __name__ == "__main__":
    print_status()
