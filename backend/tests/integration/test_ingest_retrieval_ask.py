"""End-to-end on real PostgreSQL/pgvector with a deterministic fake embedding provider.

Real: Postgres, pgvector, migrations, the PSI chunks file in data/psi_corpus/out (if built),
SQL retrieval, the /ask route. Fake: embeddings (word hashing) and the LLM reply.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.config import get_settings
from app.db import get_session
from app.main import app
from app.models import Chunk, Document
from app.services import llm, rag, retrieval
from pipeline import ingest
from tests.fakes import HashingProvider

MODEL_ID = "fake:hash:1536"
REAL_PSI = Path(__file__).resolve().parents[3] / "data" / "psi_corpus" / "out" / "chunks.jsonl"


@pytest.fixture()
def provider(monkeypatch):
    p = HashingProvider()
    for mod, name in [
        (ingest, "embedding_id"),
        (llm, "embedding_id"),
    ]:
        monkeypatch.setattr(mod, name, lambda: MODEL_ID)
    monkeypatch.setattr(retrieval, "get_embedder", lambda: p)
    monkeypatch.setattr(rag, "get_provider", lambda: p)
    monkeypatch.setattr(get_settings(), "retrieval_min_score", 0.15)
    return p


def write_psi(path: Path) -> Path:
    rows = [
        {
            "chunk_id": "psi-102#00",
            "doc_id": "psi-102",
            "psi_id": "PSI-102",
            "title": "SAME",
            "source_type": "psi_investigation",
            "source_url": "https://psi.example/102",
            "doi": "10.1/same",
            "fuel_category": "gas",
            "pillars": ["fire_safety"],
            "fire_safety_tier": 1,
            "section": "overview",
            "text": "SAME smoke aerosol measurement experiment studies smoke particle size "
            "in microgravity. ; curated habitat relevance: team opinion",
        },
        {
            "chunk_id": "psi-102#01",
            "doc_id": "psi-102",
            "psi_id": "PSI-102",
            "title": "SAME",
            "source_type": "psi_investigation",
            "source_url": "https://psi.example/102",
            "section": "approach",
            "text": "SAME flew smoke generators aboard the ISS Cygnus vehicle.",
        },
        {
            "chunk_id": "apollo-1#00",
            "doc_id": "apollo-1",
            "title": "Apollo 1 report",
            "source_type": "nasa_resource_html",
            "section": "The accident",
            "text": "Apollo 1 cabin fire occurred in a pure oxygen atmosphere during a test.",
        },
        {
            "chunk_id": "guide#00",
            "doc_id": "guide",
            "title": "Researcher's Guide",
            "source_type": "nasa_ebook_pdf",
            "section": "Page 7",
            "source_url": "https://nasa.example/guide.pdf",
            "text": "Candle flames in microgravity are spherical and dim blue.",
        },
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    return path


def test_psi_ingest_idempotent_metadata_and_stripping(db, provider, tmp_path) -> None:
    f = write_psi(tmp_path / "chunks.jsonl")
    r1 = ingest.ingest_psi(db, provider, f)
    assert r1["new"] == 4 and r1["documents"] == 3
    r2 = ingest.ingest_psi(db, provider, f)
    assert r2["new"] == 0 and r2["unchanged"] == 4 and provider.embed_calls == 3

    doc = db.scalar(select(Document).where(Document.external_id == "PSI-102"))
    assert doc.source_type == "psi" and doc.ntrs_id is None and doc.doi == "10.1/same"
    ch = db.scalar(select(Chunk).where(Chunk.chunk_key == "psi-102#00"))
    assert "curated" not in ch.content and "team opinion" not in ch.content
    assert ch.meta["curated_habitat_relevance"] == "team opinion"
    assert ch.meta["fire_safety_tier"] == 1 and ch.meta["pillars"] == ["fire_safety"]
    assert ch.page is None and ch.embedding_model == MODEL_ID
    guide = db.scalar(select(Chunk).where(Chunk.chunk_key == "guide#00"))
    assert guide.page == 7
    # no URL, no DOI: stored as NULL, nothing fabricated
    apollo = db.scalar(select(Document).where(Document.external_id == "apollo-1"))
    assert apollo.url is None and apollo.doi is None and apollo.source_type == "nasa_resource"


def test_resume_after_crash_and_force_keeps_rows(db, provider, tmp_path) -> None:
    f = write_psi(tmp_path / "chunks.jsonl")
    provider.fail_on_call = 2  # the 2nd document's embedding fails
    with pytest.raises(ValueError):
        ingest.ingest_psi(db, provider, f)
    db.rollback()
    assert db.scalar(select(func.count(Chunk.id))) == 2  # first document was saved
    provider.fail_on_call = None
    r = ingest.ingest_psi(db, provider, f)
    assert r["unchanged"] == 2 and r["new"] == 2

    ids = set(db.scalars(select(Chunk.id)))
    r = ingest.ingest_psi(db, provider, f, force=True)
    assert r["reembedded"] == 4 and set(db.scalars(select(Chunk.id))) == ids  # nothing deleted


def test_stale_chunks_pruned_only_with_prune(db, provider, tmp_path) -> None:
    f = write_psi(tmp_path / "chunks.jsonl")
    ingest.ingest_psi(db, provider, f)
    lines = f.read_text(encoding="utf-8").splitlines()
    f.write_text("\n".join(line for line in lines if "psi-102#01" not in line), encoding="utf-8")
    assert ingest.ingest_psi(db, provider, f, prune=False)["pruned"] == 0
    assert db.scalar(select(func.count(Chunk.id))) == 4
    assert ingest.ingest_psi(db, provider, f)["pruned"] == 1
    assert db.scalar(select(func.count(Chunk.id))) == 3


def test_mock_overwrite_guard(db, provider, tmp_path) -> None:
    from pipeline.sync import guard_against_mock_overwrite

    ingest.ingest_psi(db, provider, write_psi(tmp_path / "c.jsonl"))
    with pytest.raises(SystemExit):
        guard_against_mock_overwrite(db, "mock:hash:1536")


def make_ntrs_data(root: Path) -> None:
    (root / "ntrs" / "text").mkdir(parents=True)
    (root / "ntrs" / "catalog.csv").write_text(
        "id,title,authors,year,url,pdf_url\n"
        "20150023456,FLEX flame report,A. Smith;B. Jones,2015,"
        "https://ntrs.nasa.gov/citations/20150023456,https://ntrs.nasa.gov/x.pdf\n"
        "20210015913,Scanned report,,2021,https://ntrs.nasa.gov/citations/20210015913,\n",
        encoding="utf-8",
    )
    page = "Droplet flames burn with a spherical symmetry in microgravity experiments. " * 8
    (root / "ntrs" / "text" / "20150023456.jsonl").write_text(
        "\n".join(json.dumps({"page": p, "text": page}) for p in (1, 2))
        + "\n"
        + json.dumps({"page": 3, "text": ""}),
        encoding="utf-8",
    )
    (root / "ntrs" / "text" / "20210015913.jsonl").write_text(
        json.dumps({"page": 1, "text": page}), encoding="utf-8"
    )


def test_ntrs_ingest_pages_prefix_exclusion_idempotence(
    db, provider, tmp_path, monkeypatch
) -> None:
    make_ntrs_data(tmp_path)
    monkeypatch.setattr(ingest, "DATA_DIR", tmp_path)
    r = ingest.ingest_ntrs(db, provider)
    assert r["documents"] == 1 and r["skipped"] == 1  # 20210015913 is excluded
    assert db.scalar(select(Document).where(Document.external_id == "20210015913")) is None
    pages = sorted(set(db.scalars(select(Chunk.page))))
    assert pages == [1, 2]  # empty page 3 dropped, chunks never cross pages
    doc = db.scalar(select(Document))
    assert doc.source_type == "ntrs" and doc.ntrs_id == "20150023456" and doc.year == 2015
    calls = provider.embed_calls
    r2 = ingest.ingest_ntrs(db, provider)
    assert r2["new"] == 0 and r2["unchanged"] > 0 and provider.embed_calls == calls


def test_retrieval_filters_gate_and_model_isolation(db, provider, tmp_path) -> None:
    ingest.ingest_psi(db, provider, write_psi(tmp_path / "c.jsonl"))
    hits = retrieval.search(db, "SAME smoke aerosol experiment particle size", k=3)
    assert hits and hits[0].ntrs_id == "PSI-102" and hits[0].source_type == "psi"
    assert hits[0].page is None and hits[0].meta["fuel_category"] == "gas"

    only_res = retrieval.search(db, "cabin fire oxygen", source_types=["nasa_resource"])
    assert only_res and all(h.source_type == "nasa_resource" for h in only_res)
    assert not retrieval.search(db, "cabin fire oxygen", source_types=["ntrs"])
    by_meta = retrieval.search(db, "smoke", meta_filters={"fuel_category": "gas"})
    assert by_meta and all(h.meta.get("fuel_category") == "gas" for h in by_meta)

    monkeypatch_max = get_settings()
    old, monkeypatch_max.retrieval_max_per_doc = monkeypatch_max.retrieval_max_per_doc, 1
    try:
        one = retrieval.search(db, "SAME smoke aerosol particle size ISS Cygnus", k=5)
        assert len([h for h in one if h.ntrs_id == "PSI-102"]) == 1  # per-document cap
    finally:
        monkeypatch_max.retrieval_max_per_doc = old

    # out-of-corpus: nothing reaches the similarity gate
    assert retrieval.search(db, "recette tarte pommes cannelle four") == []

    # vectors from another embedding setup are never compared with the query
    db.execute(Chunk.__table__.update().values(embedding_model="other:model:1536"))
    db.commit()
    assert retrieval.search(db, "SAME smoke aerosol experiment particle size") == []


@pytest.fixture()
def client(db):
    app.dependency_overrides[get_session] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_ask_end_to_end_mixed_sources(db, provider, client, tmp_path, monkeypatch) -> None:
    make_ntrs_data(tmp_path / "d")
    monkeypatch.setattr(ingest, "DATA_DIR", tmp_path / "d")
    ingest.ingest_ntrs(db, provider)
    ingest.ingest_psi(db, provider, write_psi(tmp_path / "c.jsonl"))

    def reply(messages):  # cites passages by number, plus one passage that does not exist
        return json.dumps(
            {
                "answer": "SAME studies smoke particle size [PASSAGE 1]. Droplet flames are "
                "spherical [PASSAGE 2, PASSAGE 3]. Invented claim [PASSAGE 99].",
                "insufficient_data": False,
            }
        )

    provider.reply = reply
    monkeypatch.setattr(get_settings(), "llm_provider", "gemini")
    r = client.post("/ask", json={"question": "SAME smoke particle size and droplet flame shape"})
    assert r.status_code == 200, r.text
    body = r.json()
    prompt = provider.prompts[-1]
    assert "[PASSAGE 1]" in prompt and "Source: " in prompt
    assert "[PASSAGE 99]" not in body["answer"] and "[MOCK" not in body["answer"]
    assert body["insufficient_data"] is False
    assert all(c["ntrs_id"] for c in body["citations"])
    for c in body["citations"]:
        assert (c["page"] is None) == (c["source_type"] != "ntrs")
    retrieved_ids = {c["ntrs_id"] for c in body["citations"]}
    assert retrieved_ids <= {"PSI-102", "20150023456", "apollo-1", "guide"}


def test_ask_out_of_corpus_and_uncited(db, provider, client, tmp_path) -> None:
    ingest.ingest_psi(db, provider, write_psi(tmp_path / "c.jsonl"))
    r = client.post("/ask", json={"question": "Quelle est la recette de la tarte aux pommes ?"})
    body = r.json()
    assert body["insufficient_data"] is True and body["citations"] == []
    assert body["answer"] == "Les sources indexées ne couvrent pas cette question."
    assert provider.prompts == []  # the LLM is not even called
