"""AI 'key differences' between experiments, grounded in retrieved passages and cached."""

import json
import logging
import re

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AICache
from app.schemas import Citation, CompareInsights, ExperimentDetail, InsightPoint
from app.services import rag, retrieval
from app.services.llm import MockProvider, get_provider

log = logging.getLogger(__name__)

PER_EXPERIMENT = 4

INSTRUCTION = """Compare these NASA experiments: {names}.
Write in English. Give 3 or 4 short points (one or two sentences each) on the key differences
that matter for spacecraft and habitat fire safety: scale, fuel, flow, atmosphere, and what
each one can and cannot tell us.
Return them in "answer" as separate lines, each starting with "- " and ending with one or two
passage tags such as [PASSAGE 2]. Use a given passage in one point only.
Only state what the passages support. Do not write points about the passages themselves or
about missing data: if something is not covered, leave it out."""

CACHE_VERSION = "v2"  # bump when the prompt or post-processing changes, to regenerate
MAX_CITES_PER_POINT = 2
# Points that talk about the sources instead of the experiments are dropped.
META = re.compile(
    r"\b(passages?|provided (text|sources)|insufficient|not (enough|sufficient))\b", re.I
)
CITE_TAG = re.compile(r"\s*\[[A-Za-z0-9][\w.-]*(?:, p\.\s?\d+)?\]")


def _from_findings(experiments: list[ExperimentDetail]) -> list[InsightPoint]:
    """No-LLM fallback: the most confident sourced finding of each experiment."""
    points = []
    for e in experiments:
        best = max(e.findings, key=lambda f: f.confidence, default=None)
        if best is None:
            continue
        points.append(
            InsightPoint(
                text=f"{e.code}: {best.statement}",
                citations=[Citation(**s.model_dump()) for s in best.sources[:2]],
            )
        )
    return points


def _cache_get(session: Session, key: str) -> CompareInsights | None:
    try:
        row = session.get(AICache, key)
        return CompareInsights.model_validate(row.payload) if row else None
    except SQLAlchemyError:
        session.rollback()
        return None


def _cache_put(session: Session, key: str, value: CompareInsights) -> None:
    try:
        session.merge(AICache(key=key, payload=json.loads(value.model_dump_json())))
        session.commit()
    except SQLAlchemyError:
        session.rollback()


def compare_insights(session: Session, experiments: list[ExperimentDetail]) -> CompareInsights:
    codes = [e.code for e in experiments]
    provider = get_provider()
    if isinstance(provider, MockProvider) or len(experiments) < 2:
        return CompareInsights(
            codes=codes, points=_from_findings(experiments), generated_by="findings"
        )

    key = f"compare:{CACHE_VERSION}:{get_settings().llm_provider}:{','.join(sorted(codes))}"
    if cached := _cache_get(session, key):
        return cached

    chunks: list[retrieval.RetrievedChunk] = []
    for e in experiments:
        query = f"{e.name} ({e.code}) experiment results conditions fire safety"
        for c in retrieval.search(session, query, k=PER_EXPERIMENT):
            if c not in chunks:
                chunks.append(c)
    names = ", ".join(f"{e.code} ({e.name})" for e in experiments)
    result = rag.grounded_completion(INSTRUCTION.format(names=names), chunks)

    points: list[InsightPoint] = []
    # One point per line; if the model returned a single block, split it on " - " bullets.
    lines = result.answer.splitlines()
    if len([ln for ln in lines if ln.strip()]) < 2:
        lines = re.split(r"\s+-\s+(?=[A-Z])", result.answer)
    for line in lines:
        line = line.strip().lstrip("-•* ").strip()
        if not line or META.search(line):
            continue
        text, cited = rag.verify_citations(line, chunks)
        if not cited:  # keep only points backed by a real source
            continue
        citations = list({(c.ntrs_id, c.page): c for c in rag.build_citations(cited)}.values())
        # Sources are shown as chips under each point, so the text itself stays clean.
        clean = CITE_TAG.sub("", text).strip()
        points.append(InsightPoint(text=clean, citations=citations[:MAX_CITES_PER_POINT]))
    if len(points) < 2:
        return CompareInsights(
            codes=codes, points=_from_findings(experiments), generated_by="findings"
        )
    out = CompareInsights(
        codes=codes, points=points, generated_by=f"llm:{get_settings().llm_provider}"
    )
    _cache_put(session, key, out)
    return out
