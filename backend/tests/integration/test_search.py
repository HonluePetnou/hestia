"""/search against a real Postgres: every group, highlighting, and test lookups."""

import pytest
from fastapi.testclient import TestClient

from app.db import get_session
from app.main import app
from app.models import Chunk, Document, Experiment, Finding, FindingSource, Outcome, TestRun


@pytest.fixture()
def client(db):
    exp = Experiment(
        code="FLEX", name="Flame Extinguishment Experiment", fuels="methanol, n-heptane"
    )
    doc = Document(
        source_type="ntrs", external_id="20150023456", ntrs_id="20150023456",
        title="Detailed Results from FLEX", pdf_url="https://ntrs.example/f.pdf",
    )  # fmt: skip
    db.add_all([exp, doc])
    db.flush()
    db.add_all(
        [
            Chunk(
                document_id=doc.id,
                page=28,
                chunk_index=0,
                chunk_key="c0",
                content="Methanol droplets extinguished by radiative heat loss in microgravity.",
            ),  # fmt: skip
            Chunk(
                document_id=doc.id,
                page=29,
                chunk_index=1,
                chunk_key="c1",
                content="Heptane cool flames persisted after visible extinction.",
            ),  # fmt: skip
            TestRun(
                experiment_id=exp.id,
                run_label="FLEX-086",
                fuel="methanol",
                oxygen_percent=12.0,
                outcome=Outcome.extinction,
                extra={"co2_mole_fraction": 0.15},
            ),  # fmt: skip
        ]
    )
    finding = Finding(
        experiment_id=exp.id, statement="Large methanol droplets extinguish radiatively."
    )
    db.add(finding)
    db.flush()
    db.add(FindingSource(finding_id=finding.id, document_id=doc.id, page=28))
    db.commit()
    app.dependency_overrides[get_session] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_groups_and_highlight(client) -> None:
    body = client.get("/search", params={"q": "methanol extinguish"}).json()
    assert [
        e["code"] for e in body["experiments"]
    ] == []  # 'methanol extinguish' is not a substring
    (doc,) = body["documents"]
    assert doc["page"] == 28 and "<mark>Methanol</mark>" in doc["snippet"]
    assert doc["url"].endswith("#page=28")
    (f,) = body["findings"]
    assert f["source_label"] == "20150023456, p.28" and f["experiment_code"] == "FLEX"


def test_prefix_while_typing(client) -> None:
    body = client.get("/search", params={"q": "cool fla"}).json()
    assert [d["page"] for d in body["documents"]] == [29]


def test_experiment_substring(client) -> None:
    assert [
        e["code"] for e in client.get("/search", params={"q": "flex"}).json()["experiments"]
    ] == ["FLEX"]


@pytest.mark.parametrize("q", ["FLEX-086", "flex 86", "methanol 12%"])
def test_test_lookup(client, q) -> None:
    (t,) = client.get("/search", params={"q": q}).json()["tests"]
    assert (
        t["run_label"] == "FLEX-086" and t["co2_percent"] == 15.0 and t["outcome"] == "extinction"
    )


def test_stop_word_acronym_still_finds_sources(client, db) -> None:
    """'SAME' is an English stop word; as an experiment code it must still match."""
    exp = Experiment(code="SAME", name="Smoke Aerosol Measurement Experiment")
    doc = Document(source_type="psi", external_id="PSI-102", title="Smoke and Aerosol (SAME)")
    db.add_all([exp, doc])
    db.flush()
    db.add(
        Chunk(
            document_id=doc.id,
            chunk_index=0,
            chunk_key="s0",
            content="SAME measured smoke particle sizes from heated Teflon.",
        )
    )
    db.commit()
    body = client.get("/search", params={"q": "SAME"}).json()
    (d,) = body["documents"]
    assert d["external_id"] == "PSI-102" and "<mark>SAME</mark>" in d["snippet"]
