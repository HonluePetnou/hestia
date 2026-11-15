import json
from pathlib import Path

import pytest

from pipeline.psi import build_documents, read_psi_chunks, strip_curated

REAL = Path(__file__).resolve().parents[2] / "data" / "psi_corpus" / "out" / "chunks.jsonl"


def test_strip_curated_keeps_nasa_text() -> None:
    clean, note = strip_curated("Objective: study flames.; curated habitat relevance: moon yes")
    assert clean == "Objective: study flames." and note == "moon yes"
    assert strip_curated("plain text") == ("plain text", None)


def test_invalid_lines_and_duplicates_reported(tmp_path: Path) -> None:
    good = {"chunk_id": "a#0", "doc_id": "a", "title": "T", "text": "x"}
    f = tmp_path / "c.jsonl"
    f.write_text(
        "\n".join([json.dumps(good), "{not json", json.dumps({"doc_id": "a"}), json.dumps(good)]),
        encoding="utf-8",
    )
    records, errors = read_psi_chunks(f)
    assert len(records) == 1 and len(errors) == 3


def test_missing_doi_url_and_page_are_none(tmp_path: Path) -> None:
    f = tmp_path / "c.jsonl"
    f.write_text(
        json.dumps(
            {
                "chunk_id": "r#0",
                "doc_id": "r",
                "title": "T",
                "text": "x",
                "source_type": "nasa_resource_html",
            }
        ),
        encoding="utf-8",
    )
    (doc,) = build_documents(read_psi_chunks(f)[0])
    assert doc.url is None and doc.doi is None and doc.chunks[0].page is None
    assert doc.source_type == "nasa_resource" and doc.external_id == "r"


@pytest.mark.skipif(not REAL.exists(), reason="data/psi_corpus/out/chunks.jsonl not built")
def test_real_corpus_is_read_unchanged() -> None:
    records, errors = read_psi_chunks(REAL)
    assert errors == [] and len(records) == 323
    docs = build_documents(records)
    assert sum(len(d.chunks) for d in docs) == 323
    assert {d.source_type for d in docs} == {"psi", "nasa_resource"}
    assert not any("curated habitat" in c.content for d in docs for c in d.chunks)
    psi = next(d for d in docs if d.external_id == "PSI-102")
    assert psi.meta["curated_fields"] == ["fire_safety_tier", "pillars"]
    guide_pages = [
        c.page for d in docs for c in d.chunks if d.external_id.startswith("researchers")
    ]
    assert any(p is not None for p in guide_pages)
