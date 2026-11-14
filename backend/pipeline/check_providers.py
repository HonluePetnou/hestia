"""Live check of the configured AI providers: run this first at the hackathon.

    make check-llm        (or: uv run python -m pipeline.check_providers)

Verifies, with your real keys: the chat model answers (JSON mode), the embedding model
answers, vector size == EMBEDDING_DIM (the database column), and, for Gemini, that the
configured model names exist for this key. Model names change over time; this is the
authoritative test, not the defaults in the code.
"""

import json
import sys

from app.config import get_settings
from app.services.llm import (
    MockProvider,
    check_dimension,
    embedding_id,
    embedding_provider_name,
    get_embedder,
    get_provider,
)


def _gemini_models(client) -> set[str]:
    return {m.name.removeprefix("models/") for m in client.models.list() if m.name}


def main() -> int:
    s = get_settings()
    ok = True
    chat, emb = get_provider(), get_embedder()
    print(f"chat provider      : {s.llm_provider} ({getattr(chat, 'model', 'n/a')})")
    print(f"embedding provider : {embedding_provider_name()} -> {embedding_id()}")
    if isinstance(chat, MockProvider) and isinstance(emb, MockProvider):
        print("Both providers are the mock: set LLM_PROVIDER / keys in .env to test real ones.")
        return 0

    for label, prov, attr in (("chat", chat, "model"), ("embedding", emb, "embedding_model")):
        client, name = getattr(prov, "client", None), getattr(prov, attr, None)
        if prov.__class__.__name__ == "GeminiProvider" and client and name:
            try:
                known = _gemini_models(client)
                present = name in known
                print(f"[{'OK' if present else 'WARN'}] {label} model '{name}' "
                      f"{'is' if present else 'is NOT'} listed for this key")  # fmt: skip
                ok &= present
            except Exception as exc:
                print(f"[WARN] could not list Gemini models: {exc.__class__.__name__}")

    if not isinstance(emb, MockProvider):
        try:
            vecs = emb.embed(["microgravity flame spread"], task="query")
            check_dimension(vecs, s.embedding_dim)
            print(f"[OK] embeddings: size {len(vecs[0])} == EMBEDDING_DIM")
        except Exception as exc:
            ok = False
            print(f"[FAIL] embeddings: {exc.__class__.__name__}: {str(exc)[:300]}")

    if not isinstance(chat, MockProvider):
        try:
            schema = {
                "type": "object",
                "properties": {"answer": {"type": "string"}},
                "required": ["answer"],
            }
            raw = chat.complete(
                "Reply with JSON only.",
                [{"role": "user", "content": 'Return {"answer": "ok"}.'}],
                json_schema=schema,
            )
            json.loads(raw)
            print(f"[OK] chat JSON mode: {raw[:80]!r}")
        except Exception as exc:
            ok = False
            print(f"[FAIL] chat: {exc.__class__.__name__}: {str(exc)[:300]}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
