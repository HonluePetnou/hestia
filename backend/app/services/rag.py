"""Grounded answers: retrieve NASA passages, ask the LLM, keep only verifiable citations.

Every citation in an answer must point to a (ntrs_id, page) that was actually
retrieved. Anything else is stripped before the answer reaches the user. With no
relevant passage, or when the model says the sources are not enough, the response
is flagged `insufficient_data`.
"""

import json
import logging
import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.services import retrieval
from app.services.llm import LLMError, MockProvider, get_provider
from app.services.retrieval import RetrievedChunk

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Hestia, an assistant for spacecraft fire safety research.
You answer questions about NASA microgravity combustion experiments (BASS, Saffire, SAME,
FLEX, ACME and related work) for engineers planning Moon and Mars missions.

Rules:
- Use ONLY the numbered SOURCES provided. Never use outside knowledge for facts or numbers.
- After every factual sentence, cite its source exactly as [NTRS-ID, p.PAGE], using the
  NTRS ID and page shown in the source header, e.g. [20150023456, p.12].
- If the sources do not contain the answer, set insufficient_data to true and say briefly
  what is missing. Do not guess.
- Be concise: 2 to 6 sentences, plain English, no markdown headings.
- When relevant, say what the result implies for lunar (0.17 g) or martian (0.38 g) habitats,
  but only if a source supports it."""

ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "insufficient_data": {"type": "boolean"},
    },
    "required": ["answer", "insufficient_data"],
}

INSUFFICIENT_MESSAGE = (
    "The NASA sources indexed in Hestia do not contain enough information to answer this question."
)

_CITATION = re.compile(r"\[\s*(?:NTRS[-\s]?)?(\d{8,11})\s*,\s*p(?:age|p)?\.?\s*(\d+)\s*\]", re.I)
_ANY_BRACKET_CITE = re.compile(r"\s*\[[^\]]*\bp\.?\s*\d+[^\]]*\]")


@dataclass
class CitedAnswer:
    answer: str
    citations: list[RetrievedChunk]
    insufficient_data: bool


def format_sources(chunks: list[RetrievedChunk]) -> str:
    return "\n\n".join(
        f"SOURCE {i} — [{c.ntrs_id}, p.{c.page}] {c.title}\n{c.content}"
        for i, c in enumerate(chunks, 1)
    )


def verify_citations(text: str, chunks: list[RetrievedChunk]) -> tuple[str, list[RetrievedChunk]]:
    """Normalize valid citations, strip invented ones, return (text, cited chunks in order)."""
    allowed = {(c.ntrs_id, c.page): c for c in chunks}
    cited: list[RetrievedChunk] = []

    def repl(m: re.Match) -> str:
        key = (m.group(1), int(m.group(2)))
        if key not in allowed:
            log.info("Dropped unverifiable citation %s", key)
            return "\x00"
        if allowed[key] not in cited:
            cited.append(allowed[key])
        return f"[{key[0]}, p.{key[1]}]"

    text = _CITATION.sub(repl, text)
    text = re.sub(r"\s*\x00", "", text)
    # any remaining bracketed page reference that did not match a real source
    text = _ANY_BRACKET_CITE.sub(lambda m: m.group(0) if _CITATION.search(m.group(0)) else "", text)
    return text.strip(), cited


def _first_sentences(text: str, n: int = 2, max_chars: int = 320) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    out = " ".join(sentences[:n])
    return out if len(out) <= max_chars else out[:max_chars].rsplit(" ", 1)[0] + "…"


def _mock_answer(chunks: list[RetrievedChunk]) -> str:
    """Extractive answer used with LLM_PROVIDER=mock: quotes the top passages verbatim."""
    parts = [f"{_first_sentences(c.content)} [{c.ntrs_id}, p.{c.page}]" for c in chunks[:2]]
    return "[MOCK — extractive, no LLM] " + " ".join(parts)


def grounded_completion(
    instruction: str, chunks: list[RetrievedChunk], history: list[dict] | None = None
) -> CitedAnswer:
    """Ask the LLM `instruction` over `chunks`; return a verified, cited answer."""
    if not chunks:
        return CitedAnswer(INSUFFICIENT_MESSAGE, [], True)

    provider = get_provider()
    if isinstance(provider, MockProvider):
        text, cited = verify_citations(_mock_answer(chunks), chunks)
        return CitedAnswer(text, cited, not cited)

    prompt = f"SOURCES:\n\n{format_sources(chunks)}\n\nQUESTION: {instruction}"
    messages = [*(history or []), {"role": "user", "content": prompt}]
    raw = provider.complete(SYSTEM_PROMPT, messages, json_schema=ANSWER_SCHEMA)
    try:
        data = json.loads(raw)
        answer, insufficient = str(data["answer"]), bool(data["insufficient_data"])
    except (json.JSONDecodeError, KeyError, TypeError):
        log.warning("LLM did not return the expected JSON; using raw text")
        answer, insufficient = raw, False

    text, cited = verify_citations(answer, chunks)
    if insufficient or not cited:
        return CitedAnswer(text or INSUFFICIENT_MESSAGE, cited, True)
    return CitedAnswer(text, cited, False)


def ask(session: Session, question: str, history: list[dict] | None = None) -> CitedAnswer:
    """Answer a user question from the indexed NASA corpus.

    Raises LLMError when the provider is misconfigured or unavailable.
    """
    # Short follow-ups ("and on Mars?") retrieve better with the previous question attached.
    last_user = next((m["content"] for m in reversed(history or []) if m["role"] == "user"), "")
    query = f"{last_user} {question}" if last_user and len(question.split()) < 8 else question
    try:
        chunks = retrieval.search(session, query)
        return grounded_completion(question, chunks, history)
    except LLMError:
        raise
    except Exception as exc:  # vendor SDK errors (rate limit, network) surface as 503
        raise LLMError(f"The language model is unavailable: {exc.__class__.__name__}") from exc
