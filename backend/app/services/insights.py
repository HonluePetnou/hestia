"""AI 'key differences' between experiments, grounded in retrieved passages and cached."""

import json
import logging

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
Write 3 or 4 short points on the key differences that matter for spacecraft and habitat
fire safety (scale, fuel, flow, atmosphere, what each one can and cannot tell us).
Return them in "answer" as separate lines, each starting with "- " and each ending with
at least one citation, written as passage tags such as [PASSAGE 2]."""


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

    key = f"compare:{get_settings().llm_provider}:{','.join(sorted(codes))}"
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
    for line in result.answer.splitlines():
        line = line.strip().lstrip("-•* ").strip()
        if not line:
            continue
        text, cited = rag.verify_citations(line, chunks)
        if cited:  # keep only points backed by a real source
            points.append(
                InsightPoint(
                    text=text,
                    citations=rag.build_citations(cited),
                )
            )
    if not points:
        return CompareInsights(
            codes=codes, points=_from_findings(experiments), generated_by="findings"
        )
    out = CompareInsights(
        codes=codes, points=points, generated_by=f"llm:{get_settings().llm_provider}"
    )
    _cache_put(session, key, out)
    return out
