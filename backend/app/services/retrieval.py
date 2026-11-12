"""Retrieval over `chunks.embedding` (pgvector). Stub — implemented during the hackathon."""

from dataclasses import dataclass

from sqlalchemy.orm import Session


@dataclass
class RetrievedChunk:
    ntrs_id: str
    title: str
    page: int
    content: str
    url: str
    score: float  # cosine similarity, higher is better


def search(session: Session, question: str, k: int = 8) -> list[RetrievedChunk]:
    """Return the k chunks most similar to `question`.

    TODO: embed the question with `get_provider().embed([question])`, then query
    `Chunk.embedding.cosine_distance(vec)` ordered ascending, joined to Document.
    """
    return []
