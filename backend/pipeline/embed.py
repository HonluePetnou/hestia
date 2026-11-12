"""Compute embeddings for chunks with the configured LLM provider.

Usage (from backend/):
    uv run python -m pipeline.embed [--batch-size 64]

STUB — implemented during the hackathon.
"""

import argparse

from app.services.llm import LLMProvider
from pipeline.chunk import Chunk


def embed_chunks(
    chunks: list[Chunk], provider: LLMProvider, batch_size: int = 64
) -> list[list[float]]:
    """Return one embedding per chunk, in order, calling the provider in batches.

    TODO: implement batching, retry on rate limits, and progress logging.
    """
    raise NotImplementedError


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--batch-size", type=int, default=64)
    parser.parse_args()
    raise SystemExit("TODO: pipeline.embed is not implemented yet (Phase 2).")


if __name__ == "__main__":
    main()
