from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_session
from app.schemas import CompareResponse
from app.services import catalog

router = APIRouter(tags=["compare"])


@router.get("/compare", response_model=CompareResponse)
def compare(
    codes: str = Query(..., description="Comma-separated experiment codes, e.g. BASS,FLEX"),
    session: Session = Depends(get_session),
) -> CompareResponse:
    wanted = [c.strip().upper() for c in codes.split(",") if c.strip()]
    if not wanted:
        raise HTTPException(status_code=422, detail="Provide at least one experiment code")
    by_code = {e.code.upper(): e for e in catalog.load_experiments(session)}
    return CompareResponse(
        codes=wanted,
        experiments=[by_code[c] for c in wanted if c in by_code],
        missing=[c for c in wanted if c not in by_code],
    )
