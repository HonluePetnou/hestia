from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_session
from app.schemas import RankedFinding, RankingResponse
from app.services import catalog

router = APIRouter(tags=["ranking"])


@router.get("/ranking", response_model=RankingResponse)
def ranking(
    target: Literal["moon", "mars"] = "moon", session: Session = Depends(get_session)
) -> RankingResponse:
    """Findings ranked by relevance to the target (0-1) multiplied by confidence (0-1)."""
    ranked = []
    for f in catalog.load_findings(session):
        relevance = f.relevance_moon if target == "moon" else f.relevance_mars
        ranked.append(RankedFinding(**f.model_dump(), score=round(relevance * f.confidence, 4)))
    ranked.sort(key=lambda r: r.score, reverse=True)
    return RankingResponse(target=target, findings=ranked)
