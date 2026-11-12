from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Gravity, Outcome
from app.schemas import ExperimentDetail, ExperimentList, ExperimentSummary, TestRunOut
from app.services import catalog

router = APIRouter(prefix="/experiments", tags=["experiments"])


def _run_matches(
    r: TestRunOut,
    fuel: str | None,
    gravity: Gravity | None,
    outcome: Outcome | None,
    o2_min: float | None,
    o2_max: float | None,
) -> bool:
    if fuel and (r.fuel or "").lower() != fuel.lower():
        return False
    if gravity and r.gravity != gravity:
        return False
    if outcome and r.outcome != outcome:
        return False
    o2 = r.oxygen_percent
    if o2_min is not None and (o2 is None or o2 < o2_min):
        return False
    return not (o2_max is not None and (o2 is None or o2 > o2_max))


@router.get("", response_model=ExperimentList)
def list_experiments(
    fuel: str | None = None,
    gravity: Gravity | None = None,
    outcome: Outcome | None = None,
    o2_min: float | None = Query(None, ge=0, le=100),
    o2_max: float | None = Query(None, ge=0, le=100),
    session: Session = Depends(get_session),
) -> ExperimentList:
    """Experiments with at least one test run matching all given filters."""
    filtering = any(v is not None for v in (fuel, gravity, outcome, o2_min, o2_max))
    items = [
        ExperimentSummary.model_validate(e.model_dump())
        for e in catalog.load_experiments(session)
        if not filtering
        or any(_run_matches(r, fuel, gravity, outcome, o2_min, o2_max) for r in e.test_runs)
    ]
    return ExperimentList(items=items, total=len(items))


@router.get("/{code}", response_model=ExperimentDetail)
def get_experiment(code: str, session: Session = Depends(get_session)) -> ExperimentDetail:
    exp = catalog.get_experiment(session, code)
    if exp is None:
        raise HTTPException(status_code=404, detail=f"Experiment '{code}' not found")
    return exp
