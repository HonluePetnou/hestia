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
import time
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
        from google.genai import types

        # Chat: our own retry and fallback below, so the SDK doesn't stack its own backoff on top.
        self.client = genai.Client(
            api_key=s.gemini_api_key,
            http_options=types.HttpOptions(
                timeout=30_000, retry_options=types.HttpRetryOptions(attempts=1)
            ),
        )
        # Embedding clients: the main key first, then the extra ones; rotate on quota errors.
        extra = [k.strip() for k in (s.gemini_api_keys or "").split(",") if k.strip()]
        keys = list(dict.fromkeys([k for k in [s.gemini_api_key, *extra] if k]))
        # No SDK-level retries on embeddings: on a 429 we switch key at once (the SDK's own
        # backoff made every question wait on each exhausted key).
        no_retry = types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=1))
        self.embed_clients = [genai.Client(api_key=k, http_options=no_retry) for k in keys] or [
            self.client
        ]
        self.embed_index = 0
        # Keys out of their daily quota are skipped until this monotonic time.
        self.resting: dict[int, float] = {}
        self.model = s.llm_model or "gemini-3.8-flash"
        fallbacks = [m.strip() for m in (s.llm_fallback_models or "").split(",") if m.strip()]
        self.chat_models = list(dict.fromkeys([self.model, *fallbacks]))
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
        return self._generate(contents, config)

    def _generate(self, contents, config) -> str:
        """Each model gets two tries on transient errors (5xx, 429, timeout), then the next
        model in `chat_models` takes over; a model the key can't use (404) is skipped."""
        from google.genai import errors

        last: Exception | None = None
        for model in self.chat_models:
            for attempt in range(2):
                try:
                    resp = self.client.models.generate_content(
                        model=model, contents=contents, config=config
                    )
                    if model != self.model:
                        log.info("Answered by fallback chat model %s", model)
                    return resp.text or ""
                except errors.ClientError as exc:
                    last = exc
                    if exc.code == 429 and attempt == 0:
                        time.sleep(1.5)
                        continue
                    if exc.code in (404, 429):
                        break  # next model
                    raise
                except Exception as exc:  # ServerError (5xx), timeouts, dropped connections
                    last = exc
                    log.warning("Chat model %s failed (%s)", model, exc.__class__.__name__)
                    if attempt == 0:
                        time.sleep(1.0)
            # this model failed twice or is unavailable: try the next one
        raise LLMError(f"All chat models failed: {last.__class__.__name__ if last else 'unknown'}")

    def embed(self, texts: list[str], task: EmbedTask = "document") -> list[list[float]]:
        from google.genai import errors, types

        config = types.EmbedContentConfig(
            output_dimensionality=self.dim,
            task_type="RETRIEVAL_QUERY" if task == "query" else "RETRIEVAL_DOCUMENT",
        )
        # Try each key at most once, starting from the one that last worked; keys that ran out
        # of their daily quota are skipped for an hour instead of being retried on every call.
        last: errors.ClientError | None = None
        n = len(self.embed_clients)
        for _ in range(n):
            i = self.embed_index
            if self.resting.get(i, 0) > time.monotonic() and n > 1:
                self.embed_index = (i + 1) % n
                continue
            try:
                resp = self.embed_clients[i].models.embed_content(
                    model=self.embedding_model, contents=texts, config=config
                )
                break
            except errors.ClientError as exc:
                if exc.code != 429 or n == 1:
                    raise
                last = exc
                if "PerDay" in str(exc):
                    self.resting[i] = time.monotonic() + 3600
                self.embed_index = (i + 1) % n
                log.warning(
                    "Gemini key #%d out of quota, switching to key #%d", i + 1, self.embed_index + 1
                )
        else:
            if last is None:  # every key is resting
                raise LLMError("All Gemini keys are out of embedding quota for today.")
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
