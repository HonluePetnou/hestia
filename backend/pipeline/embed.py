"""Compute embeddings for chunks with the configured LLM provider.

Usage (from backend/):
    uv run python -m pipeline.embed [--batch-size 50]   # dry run: embeds one file, prints dims

`pipeline.ingest` calls `embed_chunks` directly.
"""

import argparse
import logging
import time

from app.config import DATA_DIR
from app.services.llm import LLMProvider, get_provider
from pipeline.chunk import Chunk, chunk_file

log = logging.getLogger("embed")

MAX_RETRIES = 6


def _is_rate_limit(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(s in msg for s in ("429", "rate", "resource_exhausted", "quota", "503", "overload"))


def embed_texts(
    texts: list[str], provider: LLMProvider, batch_size: int = 50, pause_s: float = 0.0
) -> list[list[float]]:
    """Embed texts in batches, retrying with exponential backoff on rate limits."""
    vectors: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        for attempt in range(MAX_RETRIES):
            try:
                vectors.extend(provider.embed(batch))
                break
            except Exception as exc:
                if attempt == MAX_RETRIES - 1 or not _is_rate_limit(exc):
                    raise
                wait = min(2**attempt * 5, 90)
                log.warning("Rate limited (%s), retrying in %ss", exc.__class__.__name__, wait)
                time.sleep(wait)
        log.info("Embedded %d/%d", min(start + batch_size, len(texts)), len(texts))
        if pause_s:
            time.sleep(pause_s)
    if len(vectors) != len(texts):
        raise RuntimeError(f"Provider returned {len(vectors)} vectors for {len(texts)} texts")
    return vectors


def embed_chunks(
    chunks: list[Chunk], provider: LLMProvider, batch_size: int = 50, pause_s: float = 0.0
) -> list[list[float]]:
    """Return one embedding per chunk, in order."""
    return embed_texts([c.content for c in chunks], provider, batch_size, pause_s)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--batch-size", type=int, default=50)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    path = next(iter(sorted((DATA_DIR / "ntrs" / "text").glob("*.jsonl"))), None)
    if path is None:
        raise SystemExit("No text files. Run `make extract` first.")
    chunks = chunk_file(path)[:5]
    vectors = embed_chunks(chunks, get_provider(), args.batch_size)
    print(f"{path.stem}: embedded {len(vectors)} chunks, dim={len(vectors[0])}")


if __name__ == "__main__":
    main()
