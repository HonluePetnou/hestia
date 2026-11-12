"""Pydantic request/response schemas (PROJECT_SPEC §5.1)."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import Gravity, Outcome


class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Health -----------------------------------------------------------------


class HealthResponse(_Base):
    status: Literal["ok"] = "ok"
    db: bool


# --- Experiments ------------------------------------------------------------


class SourceRef(_Base):
    ntrs_id: str
    title: str
    page: int
    url: str


class TestRunOut(_Base):
    run_label: str | None = None
    fuel: str | None = None
    oxygen_percent: float | None = None
    pressure_kpa: float | None = None
    flow_velocity_cm_s: float | None = None
    gravity: Gravity = Gravity.microgravity
    initial_diameter_mm: float | None = None
    outcome: Outcome = Outcome.unknown
    burn_rate_k: float | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class FindingOut(_Base):
    id: int
    experiment_code: str | None = None
    statement: str
    relevance_moon: float = Field(ge=0, le=1)
    relevance_mars: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    sources: list[SourceRef] = Field(default_factory=list)


class ExperimentSummary(_Base):
    code: str
    name: str
    platform: str | None = None
    description: str | None = None
    test_run_count: int = 0


class ExperimentDetail(ExperimentSummary):
    objectives: str | None = None
    psi_doi: str | None = None
    test_runs: list[TestRunOut] = Field(default_factory=list)
    findings: list[FindingOut] = Field(default_factory=list)


class ExperimentList(_Base):
    items: list[ExperimentSummary]
    total: int


class CompareResponse(_Base):
    codes: list[str]
    experiments: list[ExperimentDetail]
    missing: list[str] = Field(default_factory=list)


# --- Ranking ----------------------------------------------------------------


class RankedFinding(FindingOut):
    score: float


class RankingResponse(_Base):
    target: Literal["moon", "mars"]
    findings: list[RankedFinding]


# --- Ask --------------------------------------------------------------------


class AskRequest(_Base):
    question: str = Field(min_length=3, max_length=2000)


class Citation(SourceRef):
    pass


class AskResponse(_Base):
    answer: str
    citations: list[Citation]
    insufficient_data: bool


# --- Predict ----------------------------------------------------------------


class PredictRequest(_Base):
    fuel: str = Field(examples=["n-heptane"])
    oxygen_percent: float = Field(gt=0, le=100, examples=[21.0])
    pressure_kpa: float = Field(gt=0, examples=[101.3])
    initial_diameter_mm: float = Field(gt=0, examples=[3.0])


class PredictResponse(_Base):
    burn_rate_k: float = Field(description="Burning-rate constant K (mm^2/s)")
    extinction_probability: float = Field(ge=0, le=1)
    model: str = Field(description="Which model produced the prediction ('mock' in Phase 1)")
