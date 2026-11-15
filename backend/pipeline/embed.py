"""Compute embeddings with the configured provider: batches, retries, dimension checks.

Usage (from backend/):
    uv run python -m pipeline.embed [--batch-size 50]   # dry run: embeds 5 chunks, prints dims

`pipeline.sync` (used by `pipeline.ingest`) calls `embed_batch` for each batch and saves the
result before starting the next one, so an interrupted run loses at most one batch.
"""

import argparse
import logging
import random
import time
from collections.abc import Callable

from app.config import DATA_DIR, get_settings
from app.services.llm import LLMProvider, check_dimension, get_embedder
from pipeline.chunk import Chunk, chunk_file

log = logging.getLogger("embed")

MAX_RETRIES = 6
BASE_DELAY_S = 5.0
MAX_DELAY_S = 90.0
RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}
_RETRYABLE_WORDS = (
    "429", "rate limit", "resource_exhausted", "quota", "overload", "unavailable",
    "timed out", "timeout", "503", "502", "500",
    # dropped connections (httpx RemoteProtocolError / ConnectError / ReadError)
    "disconnected", "connection reset", "connection aborted", "connecterror", "readerror",
)  # fmt: skip


def is_retryable(exc: Exception) -> bool:
    """True for rate limits / quota / transient server errors; False for bad requests."""
    for attr in ("status_code", "code"):
        code = getattr(exc, attr, None)
        if isinstance(code, int):
            return code in RETRYABLE_STATUS
    msg = f"{type(exc).__name__} {exc}".lower()
    return any(w in msg for w in _RETRYABLE_WORDS)


def embed_batch(
    provider: LLMProvider,
    texts: list[str],
    task: str = "document",
    max_retries: int = MAX_RETRIES,
    base_delay_s: float = BASE_DELAY_S,
    sleep: Callable[[float], None] = time.sleep,
) -> list[list[float]]:
    """Embed one batch, retrying with exponential backoff (+ jitter) on retryable errors.

    Raises the last error when retries are exhausted (e.g. a daily quota): the caller has
    already saved the previous batches, so the run can simply be restarted later.
    Always checks count and dimension before returning.
    """
    for attempt in range(max_retries):
        try:
            vectors = provider.embed(texts, task=task)  # type: ignore[call-arg]
            break
        except Exception as exc:
            if attempt == max_retries - 1 or not is_retryable(exc):
                raise
            wait = min(base_delay_s * 2**attempt, MAX_DELAY_S) * random.uniform(0.8, 1.2)
            log.warning("%s (attempt %d/%d), retrying in %.0fs", exc.__class__.__name__,
                        attempt + 1, max_retries, wait)  # fmt: skip
            sleep(wait)
    if len(vectors) != len(texts):
        raise RuntimeError(f"Provider returned {len(vectors)} vectors for {len(texts)} texts")
    check_dimension(vectors, get_settings().embedding_dim)
    return vectors


def embed_texts(
    texts: list[str], provider: LLMProvider, batch_size: int = 50, pause_s: float = 0.0
) -> list[list[float]]:
    """Embed many texts in batches (no persistence; see pipeline.sync for ingestion)."""
    vectors: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        vectors.extend(embed_batch(provider, texts[start : start + batch_size]))
        log.info("Embedded %d/%d", min(start + batch_size, len(texts)), len(texts))
        if pause_s:
            time.sleep(pause_s)
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
    vectors = embed_chunks(chunks, get_embedder(), args.batch_size)
    print(f"{path.stem}: embedded {len(vectors)} chunks, dim={len(vectors[0])}")


if __name__ == "__main__":
    main()
