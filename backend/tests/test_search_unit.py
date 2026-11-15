"""/search helpers that need no database."""

from fastapi.testclient import TestClient

from app.main import app
from app.routers.search import prefix_tsquery

client = TestClient(app)


def test_prefix_query_ands_words_and_prefixes_the_last() -> None:
    assert prefix_tsquery("smoke detec") == "smoke & detec:*"
    assert prefix_tsquery("n-heptane") == "nheptane:*"
    assert prefix_tsquery("  !!  ") is None


def test_one_character_returns_empty_groups_without_searching() -> None:
    body = client.get("/search", params={"q": "s"}).json()
    assert body == {"query": "s", "experiments": [], "findings": [], "documents": [], "tests": []}


def test_empty_query_is_rejected() -> None:
    assert client.get("/search", params={"q": ""}).status_code == 422
