"""Grounded answers: retrieve NASA passages, ask the LLM, keep only verifiable citations.

The LLM sees numbered passages ([PASSAGE 1], [PASSAGE 2], ...) and cites them by number. The
backend then rebuilds every citation from database metadata (source id, page when one exists,
URL, DOI): the model never writes ids, pages or links that reach the user. A reference to a
passage that was not sent is removed. With no relevant passage, or when no valid citation
survives, the response is flagged `insufficient_data`.
"""

import json
import logging
import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.schemas import Citation
from app.services import retrieval
from app.services.llm import LLMError, MockProvider, get_provider
from app.services.retrieval import RetrievedChunk

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Hestia, an assistant for spacecraft fire safety research.
You answer questions about NASA microgravity combustion research (BASS, Saffire, SAME, FLEX,
ACME, SPICE, CFI-G and related work) for engineers planning Moon and Mars missions.

You receive numbered PASSAGES extracted from NASA sources (NTRS reports, PSI investigation
pages and other NASA resources). Rules:
1. Answer ONLY from the PASSAGES. Never use outside knowledge for facts.
2. Never invent an experimental result, a numeric value, a unit, a DOI, a URL or a reference.
3. Distinguish measured results from hypotheses, objectives and interpretations.
4. State the experimental conditions (fuel, oxygen, pressure, flow, platform) when the
   passages give them. Do not compare results obtained under incompatible conditions.
5. Passages about an "experimental table" only show sample rows, never the full table: do not
   generalize from them.
6. Say clearly what the passages do not contain. If they are not enough to answer, set
   insufficient_data to true, say briefly what is missing and do not guess.
7. Cite after every factual sentence with the passage tags only, e.g. [PASSAGE 2] or
   [PASSAGE 2, PASSAGE 5]. Never write source ids, page numbers, DOIs or URLs yourself: the
   system adds them.
8. Only say what a result implies for lunar (0.17 g) or martian (0.38 g) habitats if a
   passage supports it, and name the limits.
9. Be concise (2 to 6 sentences), clear scientific language, no markdown headings.
10. Answer in the language of the question (French question -> French answer)."""

ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "insufficient_data": {"type": "boolean"},
    },
    "required": ["answer", "insufficient_data"],
}

INSUFFICIENT_MESSAGE_FR = "Les sources indexées ne couvrent pas cette question."
INSUFFICIENT_MESSAGE_EN = "The indexed sources do not cover this question."
INSUFFICIENT_MESSAGE = INSUFFICIENT_MESSAGE_EN  # backward-compatible name

_FR_WORDS = {
    "le", "la", "les", "des", "est", "sont", "quel", "quelle", "quels", "quelles", "comment",
    "pourquoi", "une", "du", "que", "qui", "dans", "pour", "avec", "peut", "où", "quoi",
    "combien", "lors", "entre", "sur",
}  # fmt: skip

_SOURCE_LABEL = {
    "ntrs": "NTRS report",
    "psi": "PSI investigation",
    "nasa_resource": "NASA resource",
}

_ID = r"[A-Za-z0-9][\w\-\.]{0,63}"
_BRACKET = re.compile(r"\[([^\[\]\n]{1,160})\]")
_PASSAGE_REF = re.compile(
    r"\s*(?:passages?\s*|p\s*)?\d+(?:\s*[,;]\s*(?:passages?\s*|p\s*)?\d+)*\s*", re.I
)
_PAGED_REF = re.compile(rf"\s*(?:NTRS[-\s]?)?({_ID})\s*,\s*p(?:age|p)?\.?\s*(\d+)\s*", re.I)
_BARE_ID = re.compile(rf"\s*(?:NTRS[-\s]?)?({_ID})\s*")
_HAS_PAGE = re.compile(r"\bp(?:age|p)?\.?\s*\d+", re.I)


@dataclass
class CitedAnswer:
    answer: str
    citations: list[RetrievedChunk]
    insufficient_data: bool
    raw_citation_refs: int = 0  # citation-like references the model wrote
    invalid_citation_refs: int = 0  # ...of which did not match a passage that was sent


def is_french(text: str) -> bool:
    words = re.findall(r"[^\W\d_]+", text.lower())
    hits = sum(1 for w in words if w in _FR_WORDS)
    return hits >= 2 or (hits >= 1 and bool(re.search(r"[éèêàùçôîï]", text.lower())))


def insufficient_message(question: str) -> str:
    return INSUFFICIENT_MESSAGE_FR if is_french(question) else INSUFFICIENT_MESSAGE_EN


def cite_label(c: RetrievedChunk) -> str:
    """Canonical in-text citation. Page-less sources never get an invented page."""
    return f"[{c.ntrs_id}, p.{c.page}]" if c.page is not None else f"[{c.ntrs_id}]"


def format_sources(chunks: list[RetrievedChunk]) -> str:
    return "\n\n".join(
        f"[PASSAGE {i}]\n"
        f"Source type: {_SOURCE_LABEL.get(c.source_type, c.source_type)}\n"
        f"Source: {c.ntrs_id}\n"
        f"Title: {c.title}\n"
        f"Page: {c.page if c.page is not None else 'not available'}\n"
        f"Content: {c.content}"
        for i, c in enumerate(chunks, 1)
    )


def verify_citations(text: str, chunks: list[RetrievedChunk]) -> tuple[str, list[RetrievedChunk]]:
    """Resolve citations against the passages that were really sent.

    Accepted forms: passage tags ([PASSAGE 2], [P2], [PASSAGE 1, PASSAGE 3]), legacy
    "[id, p.N]" and a bare "[PSI-159]" when that source was retrieved. Valid ones are rewritten
    in canonical form; references to anything else are removed. Returns (text, cited chunks).
    """
    by_page = {(c.ntrs_id.lower(), c.page): c for c in reversed(chunks)}
    by_id = {c.ntrs_id.lower(): c for c in reversed(chunks)}
    cited: list[RetrievedChunk] = []

    def use(c: RetrievedChunk) -> str:
        if not any(c is x for x in cited):
            cited.append(c)
        return cite_label(c)

    def repl(m: re.Match) -> str:
        inner = m.group(1)
        if _PASSAGE_REF.fullmatch(inner):
            labels: list[str] = []
            for n in re.findall(r"\d+", inner):
                idx = int(n)
                if 1 <= idx <= len(chunks):
                    label = use(chunks[idx - 1])
                    if label not in labels:
                        labels.append(label)
                else:
                    log.info("Dropped reference to unknown passage %s", n)
            return " ".join(labels)
        if pm := _PAGED_REF.fullmatch(inner):
            c = by_page.get((pm.group(1).lower(), int(pm.group(2))))
            if c is None:
                log.info("Dropped unverifiable citation %s", inner)
                return ""
            return use(c)
        if (bm := _BARE_ID.fullmatch(inner)) and bm.group(1).lower() in by_id:
            return use(by_id[bm.group(1).lower()])
        if _HAS_PAGE.search(inner):  # looks like a page reference that matches no real source
            log.info("Dropped unverifiable citation %s", inner)
            return ""
        return m.group(0)

    out = _BRACKET.sub(repl, text)
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"\s+([.,;:!?])", r"\1", out)
    return out.strip(), cited


def count_citation_refs(raw: str, chunks: list[RetrievedChunk]) -> tuple[int, int]:
    """(citation-like references in the model's raw output, how many are invalid)."""
    total = invalid = 0
    for m in _BRACKET.finditer(raw):
        inner = m.group(1)
        if not (_PASSAGE_REF.fullmatch(inner) or _PAGED_REF.fullmatch(inner)):
            continue
        for part in re.findall(r"\d+", inner) if _PASSAGE_REF.fullmatch(inner) else [inner]:
            total += 1
            probe = f"[PASSAGE {part}]" if _PASSAGE_REF.fullmatch(inner) else f"[{inner}]"
            if not verify_citations(probe, chunks)[1]:
                invalid += 1
    return total, invalid


def build_citations(chunks: list[RetrievedChunk]) -> list[Citation]:
    """API citations rebuilt from database metadata, one per (source, page)."""
    seen: set[tuple[str, str, int | None]] = set()
    out: list[Citation] = []
    for c in chunks:
        key = (c.source_type, c.ntrs_id, c.page)
        if key in seen:
            continue
        seen.add(key)
        out.append(
            Citation(
                ntrs_id=c.ntrs_id,
                title=c.title,
                page=c.page,
                url=c.url,
                source_type=c.source_type,  # type: ignore[arg-type]
                doi=c.doi,
            )
        )
    return out


def _first_sentences(text: str, n: int = 2, max_chars: int = 320) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    out = " ".join(sentences[:n])
    return out if len(out) <= max_chars else out[:max_chars].rsplit(" ", 1)[0] + "…"


def _mock_answer(chunks: list[RetrievedChunk]) -> str:
    """Extractive answer used with LLM_PROVIDER=mock: quotes the top passages verbatim."""
    parts = [f"{_first_sentences(c.content)} {cite_label(c)}" for c in chunks[:2]]
    return "[MOCK — extractive, no LLM] " + " ".join(parts)


def grounded_completion(
    instruction: str, chunks: list[RetrievedChunk], history: list[dict] | None = None
) -> CitedAnswer:
    """Ask the LLM `instruction` over `chunks`; return a verified, cited answer."""
    if not chunks:
        return CitedAnswer(insufficient_message(instruction), [], True)

    provider = get_provider()
    if isinstance(provider, MockProvider):
        text, cited = verify_citations(_mock_answer(chunks), chunks)
        return CitedAnswer(text, cited, not cited)

    prompt = f"PASSAGES:\n\n{format_sources(chunks)}\n\nQUESTION: {instruction}"
    messages = [*(history or []), {"role": "user", "content": prompt}]
    raw = provider.complete(SYSTEM_PROMPT, messages, json_schema=ANSWER_SCHEMA)
    try:
        data = json.loads(raw)
        answer, insufficient = str(data["answer"]), bool(data["insufficient_data"])
    except (json.JSONDecodeError, KeyError, TypeError):
        log.warning("LLM did not return the expected JSON; using raw text")
        answer, insufficient = raw, False

    text, cited = verify_citations(answer, chunks)
    total, bad = count_citation_refs(answer, chunks)
    if insufficient:  # the model explains what is missing; keep the valid citations it gave
        return CitedAnswer(text or insufficient_message(instruction), cited, True, total, bad)
    if not cited:  # a scientific answer without any verifiable source is never returned
        log.info("Dropped an answer without a verifiable citation")
        return CitedAnswer(insufficient_message(instruction), [], True, total, bad)
    return CitedAnswer(text, cited, False, total, bad)


def ask(
    session: Session,
    question: str,
    history: list[dict] | None = None,
    source_types: list[str] | None = None,
) -> CitedAnswer:
    """Answer a user question from the indexed NASA corpus.

    Raises LLMError when the provider is misconfigured or unavailable.
    """
    # Short follow-ups ("and on Mars?") retrieve better with the previous question attached.
    last_user = next((m["content"] for m in reversed(history or []) if m["role"] == "user"), "")
    query = f"{last_user} {question}" if last_user and len(question.split()) < 8 else question
    try:
        chunks = retrieval.search(session, query, source_types=source_types)
        return grounded_completion(question, chunks, history)
    except LLMError:
        raise
    except Exception as exc:  # vendor SDK errors (rate limit, network) surface as 503
        raise LLMError(f"The language model is unavailable: {exc.__class__.__name__}") from exc
