"""Extract text page by page from NTRS PDFs with PyMuPDF.

Usage (from backend/):
    uv run python -m pipeline.extract_text [--force] [--min-chars-per-page 200]

Writes data/ntrs/text/<id>.jsonl (one line per page: {"page", "text"}) and
data/ntrs/extraction_report.csv, flagging documents with almost no text (scans).
"""

import argparse
import csv
import json
import logging
from pathlib import Path

import pymupdf

from app.config import DATA_DIR

NTRS_DIR = DATA_DIR / "ntrs"
REPORT_FIELDS = ["ntrs_id", "pages", "chars", "chars_per_page", "status"]

log = logging.getLogger("extract_text")


def extract_pages(pdf_path: Path) -> list[dict]:
    """Return [{"page": 1-based int, "text": str}, ...]."""
    with pymupdf.open(pdf_path) as doc:
        return [{"page": i + 1, "text": page.get_text("text")} for i, page in enumerate(doc)]


def classify(pages: int, chars: int, min_chars_per_page: int) -> str:
    if pages == 0:
        return "empty"
    return "ok" if chars / pages >= min_chars_per_page else "low_text"


def process(pdf_path: Path, text_dir: Path, force: bool, min_cpp: int) -> dict:
    ntrs_id = pdf_path.stem
    out = text_dir / f"{ntrs_id}.jsonl"
    try:
        if out.exists() and not force:
            pages = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
        else:
            pages = extract_pages(pdf_path)
            with out.open("w", encoding="utf-8") as fh:
                for p in pages:
                    fh.write(json.dumps(p, ensure_ascii=False) + "\n")
    except Exception as exc:  # corrupt PDFs must not stop the batch
        log.warning("Failed %s: %s", pdf_path.name, exc)
        return {"ntrs_id": ntrs_id, "pages": 0, "chars": 0, "chars_per_page": 0, "status": "error"}

    chars = sum(len(p["text"].strip()) for p in pages)
    n = len(pages)
    return {
        "ntrs_id": ntrs_id,
        "pages": n,
        "chars": chars,
        "chars_per_page": round(chars / n) if n else 0,
        "status": classify(n, chars, min_cpp),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--in", dest="pdf_dir", type=Path, default=NTRS_DIR / "pdf")
    parser.add_argument("--out", dest="text_dir", type=Path, default=NTRS_DIR / "text")
    parser.add_argument("--report", type=Path, default=NTRS_DIR / "extraction_report.csv")
    parser.add_argument("--min-chars-per-page", type=int, default=200)
    parser.add_argument("--force", action="store_true", help="re-extract existing files")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    pdfs = sorted(args.pdf_dir.glob("*.pdf"))
    if not pdfs:
        log.error("No PDFs in %s - run `make fetch` first.", args.pdf_dir)
        return
    args.text_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for pdf in pdfs:
        row = process(pdf, args.text_dir, args.force, args.min_chars_per_page)
        log.info(
            "%-16s %4d pages %8d chars  %s",
            row["ntrs_id"],
            row["pages"],
            row["chars"],
            row["status"],
        )
        rows.append(row)

    with args.report.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=REPORT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    flagged = [r["ntrs_id"] for r in rows if r["status"] != "ok"]
    log.info(
        "Report: %s - %d ok, %d flagged %s",
        args.report,
        len(rows) - len(flagged),
        len(flagged),
        flagged or "",
    )


if __name__ == "__main__":
    main()
