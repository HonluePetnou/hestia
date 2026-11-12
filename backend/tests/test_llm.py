import math

from app.services.llm import MockProvider


def test_mock_embeddings_deterministic_and_normalized() -> None:
    p = MockProvider(dim=1536)
    a1, b = p.embed(["flame", "smoke"])
    (a2,) = p.embed(["flame"])
    assert len(a1) == 1536
    assert a1 == a2
    assert a1 != b
    assert math.isclose(sum(v * v for v in a1), 1.0, rel_tol=1e-9)


def test_mock_complete() -> None:
    p = MockProvider(dim=8)
    assert "[MOCK]" in p.complete("sys", [{"role": "user", "content": "hi"}])
    assert p.complete("sys", [], json_schema={"type": "object"}) == '{"mock": true}'
