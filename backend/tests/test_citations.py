import pytest

from app.services import rag
from app.services.retrieval import RetrievedChunk


def ntrs(page: int = 12) -> RetrievedChunk:
    return RetrievedChunk(
        "20150023456", "FLEX report", page, "text", "https://x/y.pdf#page=12", 0.9
    )


def psi() -> RetrievedChunk:
    return RetrievedChunk(
        "PSI-159", "CFI-G", None, "text", "https://psi/159", 0.8, source_type="psi", doi="10.1/x"
    )


CHUNKS = [ntrs(), psi()]


def test_passage_tags_become_canonical_citations() -> None:
    text, cited = rag.verify_citations("A [PASSAGE 1]. B [P2]. C [PASSAGE 1, PASSAGE 2].", CHUNKS)
    assert text == ("A [20150023456, p.12]. B [PSI-159]. C [20150023456, p.12] [PSI-159].")
    assert cited == CHUNKS


def test_unknown_passage_and_forged_citations_are_removed() -> None:
    text, cited = rag.verify_citations(
        "A [PASSAGE 9]. B [99999999, p.3]. C [PSI-999]. D [Smith, p.4].", CHUNKS
    )
    assert "PASSAGE" not in text and "99999999" not in text and "Smith" not in text
    assert "[PSI-999]" in text  # unknown bare tag is plain text, never counted as a citation
    assert cited == []


def test_legacy_format_still_verified() -> None:
    text, cited = rag.verify_citations("A [20150023456, p.12] B [20150023456, p.13]", CHUNKS)
    assert "[20150023456, p.12]" in text and "p.13" not in text
    assert cited == [CHUNKS[0]]


def test_psi_never_gets_an_invented_page() -> None:
    assert rag.cite_label(psi()) == "[PSI-159]"
    text, _ = rag.verify_citations("X [PSI-159, p.3]", CHUNKS)
    assert "p.3" not in text


def test_build_citations_from_metadata_and_dedup() -> None:
    cites = rag.build_citations([ntrs(), ntrs(), psi()])
    assert [c.ntrs_id for c in cites] == ["20150023456", "PSI-159"]
    assert cites[1].page is None and cites[1].source_type == "psi" and cites[1].doi == "10.1/x"


def test_format_sources_has_internal_ids() -> None:
    out = rag.format_sources(CHUNKS)
    assert "[PASSAGE 1]" in out and "[PASSAGE 2]" in out and "Page: not available" in out


@pytest.mark.parametrize(
    ("q", "fr"),
    [("Quelle est la pression dans SAME ?", True), ("What is SAME?", False)],
)
def test_language_and_fixed_message(q: str, fr: bool) -> None:
    assert rag.is_french(q) is fr
    assert rag.insufficient_message(q) == (
        "Les sources indexées ne couvrent pas cette question."
        if fr
        else "The indexed sources do not cover this question."
    )


def test_no_chunks_means_insufficient_and_no_citations() -> None:
    res = rag.grounded_completion("Quelle est la recette ?", [])
    assert res.insufficient_data and res.citations == []


def test_answer_without_valid_citation_is_not_returned(monkeypatch) -> None:
    from tests.fakes import HashingProvider

    p = HashingProvider('{"answer": "Flames are blue [PASSAGE 7].", "insufficient_data": false}')
    monkeypatch.setattr(rag, "get_provider", lambda: p)
    res = rag.grounded_completion("What colour?", CHUNKS)
    assert res.insufficient_data and res.citations == [] and "blue" not in res.answer


def test_insufficient_answer_keeps_valid_citations(monkeypatch) -> None:
    from tests.fakes import HashingProvider

    p = HashingProvider(
        '{"answer": "Only the objective is given [PASSAGE 2].", "insufficient_data": true}'
    )
    monkeypatch.setattr(rag, "get_provider", lambda: p)
    res = rag.grounded_completion("What were the results?", CHUNKS)
    assert res.insufficient_data and res.citations == [CHUNKS[1]]
