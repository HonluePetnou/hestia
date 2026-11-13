"""Split per-page text (data/ntrs/text/*.jsonl) into retrieval chunks.

Usage (from backend/):
    uv run python -m pipeline.chunk [--max-tokens 400] [--overlap 60]

Prints a summary only; `pipeline.ingest` calls `chunk_file` directly.

Chunks never cross a page boundary, so every chunk keeps the exact page number
used in citations ([NTRS-ID, p.X]). Token counts are estimated from word counts
(~0.75 words per token), which is close enough for sizing chunks.
"""

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

from app.config import DATA_DIR

WORDS_PER_TOKEN = 0.75
MIN_CHUNK_WORDS = 25  # drop page headers, figure-only pages, etc.

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\[])")


@dataclass
class Chunk:
    ntrs_id: str
    page: int
    chunk_index: int
    content: str
    token_count: int


def estimate_tokens(text: str) -> int:
    return round(len(text.split()) / WORDS_PER_TOKEN)


def clean_text(text: str) -> str:
    """Undo PDF line wrapping: re-join hyphenated words and collapse whitespace."""
    text = text.replace("�", "-")  # dashes PyMuPDF could not decode
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", text)  # NUL etc. (Postgres rejects NUL)
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    return re.sub(r"\s+", " ", text).strip()


def _split_sentences(text: str, max_words: int) -> list[str]:
    """Sentences, with any over-long 'sentence' (tables, lists) hard-split by words."""
    out: list[str] = []
    for sentence in _SENTENCE_END.split(text):
        words = sentence.split()
        for i in range(0, len(words), max_words):
            out.append(" ".join(words[i : i + max_words]))
    return [s for s in out if s]


def chunk_pages(
    ntrs_id: str, pages: list[dict], max_tokens: int = 400, overlap: int = 60
) -> list[Chunk]:
    """Split pages ([{"page", "text"}]) into sentence-packed chunks of ~max_tokens,
    with ~overlap tokens of trailing context repeated at the start of the next chunk
    of the same page.
    """
    max_words = max(int(max_tokens * WORDS_PER_TOKEN), 20)
    overlap_words = int(overlap * WORDS_PER_TOKEN)
    chunks: list[Chunk] = []

    for p in pages:
        sentences = _split_sentences(clean_text(p.get("text", "")), max_words)
        current: list[str] = []
        current_words = 0

        for sentence in sentences:
            n = len(sentence.split())
            if current and current_words + n > max_words:
                _flush(chunks, ntrs_id, p["page"], current)
                # carry trailing sentences as overlap
                tail: list[str] = []
                tail_words = 0
                for s in reversed(current):
                    w = len(s.split())
                    if tail_words + w > overlap_words:
                        break
                    tail.insert(0, s)
                    tail_words += w
                current, current_words = tail, tail_words
            current.append(sentence)
            current_words += n
        if current:
            _flush(chunks, ntrs_id, p["page"], current)
    return chunks


def _flush(chunks: list[Chunk], ntrs_id: str, page: int, sentences: list[str]) -> None:
    content = " ".join(sentences)
    if len(content.split()) >= MIN_CHUNK_WORDS:
        chunks.append(Chunk(ntrs_id, page, len(chunks), content, estimate_tokens(content)))


def read_pages(jsonl_path: Path) -> list[dict]:
    with jsonl_path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def chunk_file(jsonl_path: Path, max_tokens: int = 400, overlap: int = 60) -> list[Chunk]:
    """Read one <id>.jsonl file and chunk it."""
    return chunk_pages(jsonl_path.stem, read_pages(jsonl_path), max_tokens, overlap)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--in", dest="text_dir", type=Path, default=DATA_DIR / "ntrs" / "text")
    parser.add_argument("--max-tokens", type=int, default=400)
    parser.add_argument("--overlap", type=int, default=60)
    args = parser.parse_args()

    total = 0
    files = sorted(args.text_dir.glob("*.jsonl"))
    for path in files:
        n = len(chunk_file(path, args.max_tokens, args.overlap))
        total += n
        print(f"{path.stem}: {n} chunks")
    print(f"{len(files)} documents, {total} chunks")


if __name__ == "__main__":
    main()
