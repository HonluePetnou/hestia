"""Provider-agnostic LLM + embeddings interface (PROJECT_SPEC §6).

Select with env `LLM_PROVIDER` = mock | openai | gemini | anthropic.
`mock` needs no key and is fully deterministic. Real providers are thin wrappers
around each vendor's official SDK, imported lazily so the mock path has no
external requirements.
"""

import hashlib
import math
import struct
from functools import lru_cache
from typing import Literal, Protocol

from app.config import Settings, get_settings

EmbedTask = Literal["document", "query"]


class LLMProvider(Protocol):
    def complete(
        self, system: str, messages: list[dict], json_schema: dict | None = None
    ) -> str: ...

    def embed(self, texts: list[str], task: EmbedTask = "document") -> list[list[float]]: ...


class LLMError(RuntimeError):
    pass


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
        self.model = s.llm_model or "gemini-2.5-flash"
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
        from google.genai import types

        resp = self.client.models.embed_content(
            model=self.embedding_model,
            contents=texts,
            config=types.EmbedContentConfig(
                output_dimensionality=self.dim,
                task_type="RETRIEVAL_QUERY" if task == "query" else "RETRIEVAL_DOCUMENT",
            ),
        )
        return [list(e.values or []) for e in resp.embeddings or []]


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


@lru_cache
def get_provider() -> LLMProvider:
    s = get_settings()
    if s.llm_provider == "mock":
        return MockProvider(s.embedding_dim)
    if not getattr(s, _KEYS[s.llm_provider]):
        raise LLMError(
            f"LLM_PROVIDER={s.llm_provider} but {_KEYS[s.llm_provider].upper()} is not set."
        )
    return _CLASSES[s.llm_provider](s)
