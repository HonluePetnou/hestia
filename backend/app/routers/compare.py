from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_session
from app.schemas import CompareInsights, CompareResponse, ExperimentDetail
from app.services import catalog, insights
from app.services.llm import LLMError

router = APIRouter(tags=["compare"])

CODES = Query(..., description="Comma-separated experiment codes, e.g. BASS,FLEX")


def _resolve(codes: str, session: Session) -> tuple[list[str], list[ExperimentDetail], list[str]]:
    wanted = [c.strip().upper() for c in codes.split(",") if c.strip()]
    if not wanted:
        raise HTTPException(status_code=422, detail="Provide at least one experiment code")
    by_code = {e.code.upper(): e for e in catalog.load_experiments(session)}
    found = [by_code[c] for c in wanted if c in by_code]
    return wanted, found, [c for c in wanted if c not in by_code]


@router.get("/compare", response_model=CompareResponse)
def compare(codes: str = CODES, session: Session = Depends(get_session)) -> CompareResponse:
    wanted, found, missing = _resolve(codes, session)
    return CompareResponse(codes=wanted, experiments=found, missing=missing)


@router.get("/compare/insights", response_model=CompareInsights)
def compare_insights(
    codes: str = CODES, session: Session = Depends(get_session)
) -> CompareInsights:
    """Key differences between experiments, each point with verified NTRS citations.

    Uses the LLM when one is configured (cached per set of codes), otherwise the
    experiments' most confident sourced findings.
    """
    _, found, _ = _resolve(codes, session)
    try:
        return insights.compare_insights(session, found)
    except LLMError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # vendor SDK errors
        raise HTTPException(status_code=503, detail="The language model is unavailable.") from exc
