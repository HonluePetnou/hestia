from fastapi import APIRouter, Depends
from sqlalchemy import distinct, func, select, tuple_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_session
from app.models import Chunk, Document, Experiment, Finding, TestRun
from app.schemas import StatsResponse
from app.services import catalog

router = APIRouter(tags=["stats"])


@router.get("/stats", response_model=StatsResponse)
def stats(session: Session = Depends(get_session)) -> StatsResponse:
    """Knowledge-base counts for the overview screen."""
    provider = get_settings().llm_provider
    try:
        docs = session.scalar(select(func.count(distinct(Chunk.document_id)))) or 0
        if docs:
            year_min, year_max = session.execute(
                select(func.min(Document.year), func.max(Document.year)).where(
                    Document.external_id.not_like("MOCK-%")
                )
            ).one()
            flex = session.scalar(
                select(func.count(TestRun.id)).join(Experiment).where(Experiment.code == "FLEX")
            )
            return StatsResponse(
                documents=docs,
                chunks=session.scalar(select(func.count(Chunk.id))) or 0,
                pages=session.scalar(
                    select(func.count(distinct(tuple_(Chunk.document_id, Chunk.page)))).where(
                        Chunk.page.is_not(None)
                    )
                )
                or 0,
                experiments=session.scalar(select(func.count(Experiment.id))) or 0,
                test_runs=session.scalar(select(func.count(TestRun.id))) or 0,
                flex_tests=flex or 0,
                findings=session.scalar(select(func.count(Finding.id))) or 0,
                year_min=year_min,
                year_max=year_max,
                llm_provider=provider,
                live_data=True,
            )
    except SQLAlchemyError:
        session.rollback()
    exps = catalog.load_experiments(session)
    return StatsResponse(
        documents=0,
        chunks=0,
        pages=0,
        experiments=len(exps),
        test_runs=sum(e.test_run_count for e in exps),
        flex_tests=sum(e.test_run_count for e in exps if e.code == "FLEX"),
        findings=sum(len(e.findings) for e in exps),
        llm_provider=provider,
        live_data=False,
    )
