import pytest

from app.services.llm import EmbeddingDimensionError, l2_normalize
from pipeline.chunk import context_prefix
from pipeline.embed import embed_batch, is_retryable
from tests.fakes import HashingProvider


class Flaky(HashingProvider):
    def __init__(self, errors: list[Exception]) -> None:
        super().__init__()
        self.errors = errors

    def embed(self, texts, task="document"):
        if self.errors:
            raise self.errors.pop(0)
        return super().embed(texts, task)


def test_backoff_then_success() -> None:
    sleeps: list[float] = []
    p = Flaky([RuntimeError("429 RESOURCE_EXHAUSTED"), RuntimeError("503 unavailable")])
    out = embed_batch(p, ["a", "b"], base_delay_s=1, sleep=sleeps.append)
    assert len(out) == 2 and len(sleeps) == 2 and sleeps[1] > sleeps[0]


def test_non_retryable_error_raises_immediately() -> None:
    sleeps: list[float] = []
    with pytest.raises(ValueError):
        embed_batch(Flaky([ValueError("bad request")]), ["a"], sleep=sleeps.append)
    assert sleeps == []


def test_retries_exhausted_raises() -> None:
    p = Flaky([RuntimeError("429")] * 10)
    with pytest.raises(RuntimeError):
        embed_batch(p, ["a"], max_retries=3, base_delay_s=0, sleep=lambda s: None)


def test_dimension_mismatch_is_refused() -> None:
    with pytest.raises(EmbeddingDimensionError):
        embed_batch(HashingProvider(dim=768), ["a"])


def test_is_retryable_uses_status_codes() -> None:
    class E(Exception):
        status_code = 400

    assert not is_retryable(E("rate limit")) and is_retryable(RuntimeError("quota exceeded"))


def test_normalize_and_prefix() -> None:
    assert l2_normalize([3.0, 4.0]) == [0.6, 0.8]
    assert context_prefix("FLEX report", 2015, 12) == "FLEX report (2015), p.12"
    assert context_prefix("PSI", None, None) == "PSI"
