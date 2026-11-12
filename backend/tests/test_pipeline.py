import json
from pathlib import Path

import pymupdf

from pipeline.extract_text import classify, process
from pipeline.fetch_ntrs import parse_record

SAMPLE = {
    "id": 20170000230,
    "title": "Operation and Development Status of the Spacecraft Fire Experiments (Saffire)",
    "authorAffiliations": [
        {"sequence": 1, "meta": {"author": {"name": "Urban, David L."}}},
        {"sequence": 0, "meta": {"author": {"name": "Ruff, Gary A."}}},
    ],
    "publications": [{"publicationDate": "2016-07-10T00:00:00.0000000+00:00"}],
    "downloads": [
        {
            "mimetype": "application/pdf",
            "links": {"pdf": "/api/citations/20170000230/downloads/20170000230.pdf"},
        }
    ],
}


def test_parse_record() -> None:
    rec = parse_record(SAMPLE)
    assert rec["id"] == "20170000230"
    assert rec["authors"] == "Ruff, Gary A.; Urban, David L."
    assert rec["year"] == 2016
    assert rec["url"] == "https://ntrs.nasa.gov/citations/20170000230"
    assert rec["pdf_url"].endswith("/api/citations/20170000230/downloads/20170000230.pdf")
    assert rec["pdf_url"].startswith("https://ntrs.nasa.gov")


def test_parse_record_without_pdf() -> None:
    rec = parse_record({"id": 1, "title": "x", "downloads": []})
    assert rec["pdf_url"] == "" and rec["year"] is None


def test_extract_text(tmp_path: Path) -> None:
    pdf = tmp_path / "123.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Flame spread in microgravity " * 20)
    doc.new_page()  # blank page
    doc.save(pdf)
    doc.close()

    row = process(pdf, tmp_path, force=True, min_cpp=200)
    lines = (tmp_path / "123.jsonl").read_text(encoding="utf-8").splitlines()
    pages = [json.loads(line) for line in lines]
    assert [p["page"] for p in pages] == [1, 2]
    assert "Flame spread" in pages[0]["text"]
    assert row["pages"] == 2 and row["ntrs_id"] == "123"


def test_classify() -> None:
    assert classify(10, 50, 200) == "low_text"
    assert classify(10, 5000, 200) == "ok"
    assert classify(0, 0, 200) == "empty"
