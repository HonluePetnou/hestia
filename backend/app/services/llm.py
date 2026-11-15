"""Provider-agnostic LLM + embeddings interface (PROJECT_SPEC §6).

Select with env `LLM_PROVIDER` = mock | openai | gemini | anthropic.
`mock` needs no key and is fully deterministic. Real providers are thin wrappers
around each vendor's official SDK, imported lazily so the mock path has no
external requirements.
"""

import hashlib
import logging
import math
import struct
from functools import lru_cache
from typing import Literal, Protocol

from app.config import Settings, get_settings

log = logging.getLogger(__name__)

EmbedTask = Literal["document", "query"]


class LLMProvider(Protocol):
    def complete(
        self, system: str, messages: list[dict], json_schema: dict | None = None
    ) -> str: ...

    def embed(self, texts: list[str], task: EmbedTask = "document") -> list[list[float]]: ...


class LLMError(RuntimeError):
    pass


class EmbeddingDimensionError(LLMError):
    """The provider returned vectors whose size differs from EMBEDDING_DIM (the DB column)."""


def l2_normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec))
    return [v / norm for v in vec] if norm else vec


def check_dimension(vectors: list[list[float]], dim: int) -> None:
    """Raise if any vector is not exactly `dim` long (never write a mismatched vector)."""
    for v in vectors:
        if len(v) != dim:
            raise EmbeddingDimensionError(
                f"Embedding size {len(v)} != EMBEDDING_DIM={dim}. Fix EMBEDDING_DIM / the model, "
                "or migrate the chunks.embedding column (see docs/RAG.md)."
            )


def embedding_id() -> str:
    """Identifier of the embedding setup ("<provider>:<model>:<dim>") stored with each chunk.

    Chunks embedded with a different id are never mixed in a search: ingestion re-embeds them.
    """
    s = get_settings()
    name = embedding_provider_name()
    if name == "mock":
        return f"mock:hash:{s.embedding_dim}"
    default = {"openai": "text-embedding-3-small", "gemini": "gemini-embedding-001"}.get(
        name, "none"
    )
    return f"{name}:{s.embedding_model or default}:{s.embedding_dim}"


def embedding_provider_name() -> str:
    s = get_settings()
    return s.embedding_provider or s.llm_provider


# --- Mock -------------------------------------------------------------------


class MockProvider:
    """Deterministic fake provider: canned answers, hash-based unit-norm embeddings."""

    CANNED_ANSWER = (
        "[MOCK] This is a placeholder answer from the mock LLM provider. "
        "No real model was called. [MOCK-0001, p.4]"
    )

    def __init__(self, dim: int) -> None:
        self.dim = dim

    def complete(self, system: str, messages: list[dict], json_schema: dict | None = None) -> str:
        if json_schema is not None:
            return '{"mock": true}'
        return self.CANNED_ANSWER

    def embed(self, texts: list[str], task: EmbedTask = "document") -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def _embed_one(self, text: str) -> list[float]:
        values: list[float] = []
        counter = 0
        while len(values) < self.dim:
            digest = hashlib.sha256(f"{counter}:{text}".encode()).digest()
            # 8 unsigned 32-bit ints per digest, mapped to [-1, 1]
            values.extend(v / 2**31 - 1.0 for v in struct.unpack("<8I", digest))
            counter += 1
        values = values[: self.dim]
        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return [v / norm for v in values]


# --- OpenAI -----------------------------------------------------------------


class OpenAIProvider:
    def __init__(self, s: Settings) -> None:
        from openai import OpenAI

        self.client = OpenAI(api_key=s.openai_api_key)
        self.model = s.llm_model or "gpt-4.1-mini"
        self.embedding_model = s.embedding_model or "text-embedding-3-small"
        self.dim = s.embedding_dim

    def complete(self, system: str, messages: list[dict], json_schema: dict | None = None) -> str:
        kwargs: dict = {}
        if json_schema is not None:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "response", "schema": json_schema},
            }
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system}, *messages],
            **kwargs,
        )
        return resp.choices[0].message.content or ""

    def embed(self, texts: list[str], task: EmbedTask = "document") -> list[list[float]]:
        resp = self.client.embeddings.create(
            model=self.embedding_model, input=texts, dimensions=self.dim
        )
        return [d.embedding for d in resp.data]


# --- Gemini -----------------------------------------------------------------


class GeminiProvider:
    def __init__(self, s: Settings) -> None:
        from google import genai

        self.client = genai.Client(api_key=s.gemini_api_key)
        # Embedding clients: the main key first, then the extra ones; rotate on quota errors.
        extra = [k.strip() for k in (s.gemini_api_keys or "").split(",") if k.strip()]
        keys = list(dict.fromkeys([k for k in [s.gemini_api_key, *extra] if k]))
        self.embed_clients = [genai.Client(api_key=k) for k in keys] or [self.client]
        self.embed_index = 0
        self.model = s.llm_model or "gemini-3.8-flash"
        self.embedding_model = s.embedding_model or "gemini-embedding-001"
        self.dim = s.embedding_dim

    def complete(self, system: str, messages: list[dict], json_schema: dict | None = None) -> str:
        from google.genai import types

        contents = [
            types.Content(
                role="model" if m["role"] == "assistant" else "user",
                parts=[types.Part(text=m["content"])],
            )
            for m in messages
        ]
        config = types.GenerateContentConfig(system_instruction=system)
        if json_schema is not None:
            config.response_mime_type = "application/json"
            config.response_json_schema = json_schema
        resp = self.client.models.generate_content(
            model=self.model, contents=contents, config=config
        )
        return resp.text or ""

    def embed(self, texts: list[str], task: EmbedTask = "document") -> list[list[float]]:
        from google.genai import errors, types

        config = types.EmbedContentConfig(
            output_dimensionality=self.dim,
            task_type="RETRIEVAL_QUERY" if task == "query" else "RETRIEVAL_DOCUMENT",
        )
        # Try each key at most once, starting from the one that last worked.
        last: errors.ClientError | None = None
        for _ in range(len(self.embed_clients)):
            client = self.embed_clients[self.embed_index]
            try:
                resp = client.models.embed_content(
                    model=self.embedding_model, contents=texts, config=config
                )
                break
            except errors.ClientError as exc:
                if exc.code != 429 or len(self.embed_clients) == 1:
                    raise
                last = exc
                self.embed_index = (self.embed_index + 1) % len(self.embed_clients)
                log.warning("Gemini key quota hit, switching to key #%d", self.embed_index + 1)
        else:
            assert last is not None
            raise last  # every key is out of quota; the caller's backoff takes over
        vectors = [list(e.values or []) for e in resp.embeddings or []]
        # Google only pre-normalizes the full 3072-dim vector; shorter (MRL) ones need it.
        return [l2_normalize(v) for v in vectors] if self.dim < 3072 else vectors


# --- Anthropic --------------------------------------------------------------


class AnthropicProvider:
    """Claude via the official SDK. Anthropic has no embeddings endpoint."""

    def __init__(self, s: Settings) -> None:
        import anthropic

        self.client = anthropic.Anthropic(api_key=s.anthropic_api_key)
        self.model = s.llm_model or "claude-opus-5-5"

    def complete(self, system: str, messages: list[dict], json_schema: dict | None = None) -> str:
        kwargs: dict = {}
        if json_schema is not None:
            kwargs["output_config"] = {"format": {"type": "json_schema", "schema": json_schema}}
        resp = self.client.beta.messages.create(
            model=self.model,
            max_tokens=16000,
            system=system,
            messages=messages,
            # Server-side fallback if the model declines (stop_reason "refusal").
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            **kwargs,
        )
        if resp.stop_reason == "refusal":
            raise LLMError("The model declined to answer this request.")
        return "".join(b.text for b in resp.content if b.type == "text")

    def embed(self, texts: list[str], task: EmbedTask = "document") -> list[list[float]]:
        raise NotImplementedError(
            "Anthropic has no embeddings API. Use LLM_PROVIDER=openai/gemini for embeddings, "
            "or add a separate embedding provider."
        )


# --- Factory ----------------------------------------------------------------

_KEYS = {"openai": "openai_api_key", "gemini": "gemini_api_key", "anthropic": "anthropic_api_key"}
_CLASSES = {"openai": OpenAIProvider, "gemini": GeminiProvider, "anthropic": AnthropicProvider}


def _build(name: str) -> LLMProvider:
    s = get_settings()
    if name == "mock":
        return MockProvider(s.embedding_dim)
    if not getattr(s, _KEYS[name]):
        raise LLMError(f"Provider '{name}' selected but {_KEYS[name].upper()} is not set.")
    return _CLASSES[name](s)


@lru_cache
def get_provider() -> LLMProvider:
    """Chat/generation provider (LLM_PROVIDER)."""
    return _build(get_settings().llm_provider)


@lru_cache
def get_embedder() -> LLMProvider:
    """Embedding provider: EMBEDDING_PROVIDER, else the same as the chat provider."""
    name = embedding_provider_name()
    return get_provider() if name == get_settings().llm_provider else _build(name)
