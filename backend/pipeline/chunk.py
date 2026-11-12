"""Split per-page text (data/ntrs/text/*.jsonl) into retrieval chunks.

Usage (from backend/):
    uv run python -m pipeline.chunk [--max-tokens 500] [--overlap 50]

STUB — the chunking strategy is decided during the hackathon.
"""

import argparse
from dataclasses import dataclass
from pathlib import Path

from app.config import DATA_DIR


@dataclass
class Chunk:
    ntrs_id: str
    page: int
    chunk_index: int
    content: str
    token_count: int


def chunk_pages(
    ntrs_id: str, pages: list[dict], max_tokens: int = 500, overlap: int = 50
) -> list[Chunk]:
    """Split pages ([{"page", "text"}]) into chunks that never cross a page boundary,
    so every chunk keeps an exact page number for citations.

    TODO: implement (e.g. paragraph-aware split with token-count overlap).
    """
    raise NotImplementedError


def chunk_file(jsonl_path: Path, max_tokens: int = 500, overlap: int = 50) -> list[Chunk]:
    """Read one <id>.jsonl file and chunk it. TODO: implement."""
    raise NotImplementedError


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--in", dest="text_dir", type=Path, default=DATA_DIR / "ntrs" / "text")
    parser.add_argument("--max-tokens", type=int, default=500)
    parser.add_argument("--overlap", type=int, default=50)
    parser.parse_args()
    raise SystemExit("TODO: pipeline.chunk is not implemented yet (Phase 2).")


if __name__ == "__main__":
    main()
