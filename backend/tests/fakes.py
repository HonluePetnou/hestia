"""Test doubles: a deterministic 'lexical' embedding provider (no network, no key)."""

import hashlib
import math
import re
from collections.abc import Callable

DIM = 1536


def _vec(text: str, dim: int = DIM) -> list[float]:
    """Feature hashing of words: cosine similarity then reflects word overlap."""
    v = [0.0] * dim
    for w in re.findall(r"\w+", text.lower()):
        v[int(hashlib.sha1(w.encode()).hexdigest(), 16) % dim] += 1.0
    norm = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / norm for x in v]


class HashingProvider:
    """Stands in for a real provider: real-looking vectors + a scripted LLM reply."""

    def __init__(self, reply: str | Callable[[list[dict]], str] = "", dim: int = DIM) -> None:
        self.dim = dim
        self.reply = reply
        self.embed_calls = 0
        self.fail_on_call: int | None = None
        self.prompts: list[str] = []

    def embed(self, texts: list[str], task: str = "document") -> list[list[float]]:
        self.embed_calls += 1
        if self.fail_on_call == self.embed_calls:
            raise ValueError("simulated provider crash")
        return [_vec(t, self.dim) for t in texts]

    def complete(self, system: str, messages: list[dict], json_schema: dict | None = None) -> str:
        self.prompts.append(messages[-1]["content"])
        return self.reply(messages) if callable(self.reply) else self.reply
