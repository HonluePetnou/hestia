"""API smoke tests. They pass with or without a database (mock-data fallback)."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert isinstance(body["db"], bool)


def test_list_experiments() -> None:
    body = client.get("/experiments").json()
    codes = {e["code"] for e in body["items"]}
    assert {"BASS", "SAFFIRE", "SAME", "FLEX", "ACME"} <= codes
    assert body["total"] == len(body["items"])


def test_filter_experiments() -> None:
    body = client.get("/experiments", params={"fuel": "n-heptane"}).json()
    assert [e["code"] for e in body["items"]] == ["FLEX"]
    body = client.get("/experiments", params={"o2_min": 29}).json()
    assert [e["code"] for e in body["items"]] == ["FLEX"]
    assert client.get("/experiments", params={"gravity": "jupiter"}).status_code == 422


def test_experiment_detail() -> None:
    body = client.get("/experiments/flex").json()
    assert body["code"] == "FLEX"
    assert body["test_runs"] and body["findings"][0]["sources"]
    assert client.get("/experiments/NOPE").status_code == 404


def test_compare() -> None:
    body = client.get("/compare", params={"codes": "BASS,FLEX,XYZ"}).json()
    assert [e["code"] for e in body["experiments"]] == ["BASS", "FLEX"]
    assert body["missing"] == ["XYZ"]


def test_ranking_sorted() -> None:
    body = client.get("/ranking", params={"target": "mars"}).json()
    scores = [f["score"] for f in body["findings"]]
    assert scores == sorted(scores, reverse=True)
    assert client.get("/ranking", params={"target": "venus"}).status_code == 422


def test_ask_mock() -> None:
    body = client.post("/ask", json={"question": "How do flames spread in microgravity?"}).json()
    assert body["answer"] and body["citations"]
    assert body["insufficient_data"] is False


def test_predict() -> None:
    payload = {
        "fuel": "n-heptane",
        "oxygen_percent": 21,
        "pressure_kpa": 101.3,
        "initial_diameter_mm": 3,
    }
    body = client.post("/predict", json=payload).json()
    assert body["burn_rate_k"] > 0
    assert 0 <= body["extinction_probability"] <= 1


def test_openapi_lists_all_routes() -> None:
    paths = client.get("/openapi.json").json()["paths"]
    for p in (
        "/health",
        "/experiments",
        "/experiments/{code}",
        "/compare",
        "/ranking",
        "/ask",
        "/predict",
    ):
        assert p in paths
