"""The validation questions must be grounded in the real corpus, not invented."""

from pathlib import Path

import pytest

from pipeline import evaluate
from pipeline.psi import build_documents, read_psi_chunks

CHUNKS = Path(__file__).resolve().parents[2] / "data" / "psi_corpus" / "out" / "chunks.jsonl"
pytestmark = pytest.mark.skipif(not CHUNKS.exists(), reason="PSI corpus not built")


def test_expected_sources_and_terms_exist_in_corpus() -> None:
    docs = {d.external_id: " ".join(c.content.lower() for c in d.chunks)
            for d in build_documents(read_psi_chunks(CHUNKS)[0])}  # fmt: skip
    questions = evaluate.load_questions()
    assert (
        len(questions) >= 20
        and sum(q["expected_behavior"] == "insufficient" for q in questions) >= 3
    )
    for q in questions:
        known = [s for s in q["expected_sources"] if s in docs]
        if not known:  # NTRS-only or out-of-corpus questions: nothing to check against PSI text
            continue
        blob = " ".join(docs[s] for s in known)
        for term in q["expected_terms"]:
            assert term.lower() in blob, f"{q['id']}: '{term}' not in {known}"
    unknown = {s for q in questions for s in q["expected_sources"]} - set(docs)
    assert all(s.isdigit() for s in unknown), f"unknown non-NTRS sources: {unknown}"


def test_question_file_is_valid_json_with_required_fields() -> None:
    for q in evaluate.load_questions():
        assert {
            "id",
            "question",
            "expected_sources",
            "needed_information",
            "expected_behavior",
        } <= q.keys()


def test_metric_helpers() -> None:
    from app.services.retrieval import RetrievedChunk

    chunk = RetrievedChunk("PSI-1", "t", None, "oxygen at 21 percent", None, 0.9)
    assert evaluate.ungrounded_numbers("It was 21 [PSI-1] and 99 percent.", [chunk]) == ["99"]
    assert (
        evaluate.unsourced_rate(
            "A sourced sentence is here [PSI-1]. An unsourced sentence is here."
        )
        == 0.5
    )
    assert evaluate.term_relevance([chunk], ["oxygen", "helium"]) == 0.5
