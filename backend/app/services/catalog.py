"""Loads experiments from the database, falling back to mock data.

The dataset is small (5 experiments, a few hundred runs), so filtering is done
in Python on top of a single eager-loaded query.
"""

import logging

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app import mock_data
from app.models import Experiment, Finding, FindingSource
from app.schemas import ExperimentDetail, FindingOut, SourceRef, TestRunOut

log = logging.getLogger(__name__)


def _to_detail(e: Experiment) -> ExperimentDetail:
    findings = [
        FindingOut(
            id=f.id,
            experiment_code=e.code,
            statement=f.statement,
            relevance_moon=f.relevance_moon,
            relevance_mars=f.relevance_mars,
            confidence=f.confidence,
            sources=[
                SourceRef(
                    ntrs_id=s.document.external_id,
                    title=s.document.title,
                    page=s.page,
                    url=s.document.page_url(s.page),
                )
                for s in f.sources
            ],
        )
        for f in e.findings
    ]
    return ExperimentDetail(
        code=e.code,
        name=e.name,
        platform=e.platform,
        description=e.description,
        objectives=e.objectives,
        psi_doi=e.psi_doi,
        years=e.years,
        fuels=e.fuels,
        finding_count=len(findings),
        test_runs=[TestRunOut.model_validate(r) for r in e.test_runs],
        test_run_count=len(e.test_runs),
        findings=findings,
    )


def load_experiments(session: Session) -> list[ExperimentDetail]:
    """All experiments with runs, findings and sources. Mock data if DB is empty/down."""
    try:
        rows = session.scalars(
            select(Experiment)
            .options(
                selectinload(Experiment.test_runs),
                selectinload(Experiment.findings)
                .selectinload(Finding.sources)
                .selectinload(FindingSource.document),
            )
            .order_by(Experiment.code)
        ).all()
        if rows:
            return [_to_detail(e) for e in rows]
    except SQLAlchemyError as exc:
        log.warning("DB unavailable, serving mock data: %s", exc.__class__.__name__)
    return mock_data.experiments()


def get_experiment(session: Session, code: str) -> ExperimentDetail | None:
    code = code.upper()
    return next((e for e in load_experiments(session) if e.code.upper() == code), None)


def load_findings(session: Session) -> list[FindingOut]:
    """Every finding, including cross-cutting ones not tied to one experiment."""
    try:
        rows = session.scalars(
            select(Finding).options(
                selectinload(Finding.experiment),
                selectinload(Finding.sources).selectinload(FindingSource.document),
            )
        ).all()
        if rows:
            return [
                FindingOut(
                    id=f.id,
                    experiment_code=f.experiment.code if f.experiment else None,
                    statement=f.statement,
                    relevance_moon=f.relevance_moon,
                    relevance_mars=f.relevance_mars,
                    confidence=f.confidence,
                    sources=[
                        SourceRef(
                            ntrs_id=s.document.external_id,
                            title=s.document.title,
                            page=s.page,
                            url=s.document.page_url(s.page),
                        )
                        for s in f.sources
                    ],
                )
                for f in rows
            ]
    except SQLAlchemyError as exc:
        log.warning("DB unavailable, serving mock findings: %s", exc.__class__.__name__)
        session.rollback()
    return [f for e in load_experiments(session) for f in e.findings]
