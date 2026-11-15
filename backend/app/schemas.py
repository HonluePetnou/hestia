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
    years: str | None = None
    fuels: str | None = None
    test_run_count: int = 0
    finding_count: int = 0


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


class ChatMessage(_Base):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class AskRequest(_Base):
    question: str = Field(min_length=3, max_length=2000)
    sources: list[Literal["ntrs", "psi", "nasa_resource"]] | None = Field(
        default=None, description="Restrict retrieval to these source types (default: all)"
    )
    history: list[ChatMessage] = Field(
        default_factory=list, description="Previous turns, oldest first (last 6 are used)"
    )


class Citation(_Base):
    """A source cited in an answer, rebuilt by the backend from database metadata.

    `ntrs_id` carries the external identifier of the source (an NTRS id, "PSI-159" or a NASA
    resource slug): the name is kept so existing clients keep working. `page` and `url` are
    null when the source has no page / no link (never invented).
    """

    ntrs_id: str
    title: str
    page: int | None = None
    url: str | None = None
    source_type: Literal["ntrs", "psi", "nasa_resource"] = "ntrs"
    doi: str | None = None


class AskResponse(_Base):
    answer: str
    citations: list[Citation]
    insufficient_data: bool


# --- Predict ----------------------------------------------------------------


class PredictRequest(_Base):
    fuel: str = Field(examples=["n-heptane"], description="n-heptane or methanol")
    oxygen_percent: float = Field(gt=0, le=100, examples=[21.0])
    pressure_kpa: float = Field(gt=0, examples=[101.3])
    initial_diameter_mm: float = Field(gt=0, examples=[3.0])
    co2_percent: float = Field(0.0, ge=0, le=100, description="CO2 diluent (suppressant)")
    he_percent: float = Field(0.0, ge=0, le=100, description="Helium diluent")


class NearestTest(_Base):
    test_id: str
    fuel: str
    oxygen_percent: float
    pressure_kpa: float
    initial_diameter_mm: float
    co2_percent: float
    he_percent: float
    outcome: str = Field(
        description="What happened on the ISS: extinction, disruption, complete_burn"
    )
    burn_rate_k: float | None = None
    extinction_diameter_mm: float | None = None
    distance: float = Field(description="Distance to the inputs in standard deviations (0 = same)")
    source_page: int | None = None
    url: str = Field(description="FLEX report PDF at the Table IX page holding this test")


class PredictResponse(_Base):
    burn_rate_k: float = Field(description="Burning-rate constant K (mm^2/s)")
    extinction_probability: float = Field(
        ge=0, le=1, description="Probability the flame goes out before the droplet burns up"
    )
    droplet_lifetime_s: float = Field(description="Estimated burn time from the d^2 law, D0^2/K")
    in_training_range: bool = Field(description="False when inputs are outside the FLEX tests")
    model: str = Field(description="Which model produced the prediction ('mock' without data)")
    nearest_test: NearestTest | None = Field(
        None, description="The real FLEX test closest to these conditions, with its ISS outcome"
    )


class ModelInfo(_Base):
    model: str
    trained: bool
    source: str
    k_samples: int = 0
    extinction_samples: int = 0
    k_r2_cv: float | None = Field(None, description="5-fold cross-validated R^2 for K")
    k_mae_cv: float | None = Field(None, description="5-fold cross-validated MAE for K (mm^2/s)")
    extinction_auc_cv: float | None = None
    extinction_balanced_accuracy_cv: float | None = None
    ranges: dict[str, tuple[float, float]] = Field(default_factory=dict)


# --- Stats ------------------------------------------------------------------


class StatsResponse(_Base):
    documents: int = Field(description="NTRS reports indexed for search")
    chunks: int = Field(description="Searchable passages")
    pages: int = Field(description="Distinct report pages covered by passages")
    experiments: int
    test_runs: int
    flex_tests: int
    findings: int
    year_min: int | None = None
    year_max: int | None = None
    llm_provider: str
    live_data: bool = Field(description="False when the API serves built-in mock data")


# --- Compare insights -------------------------------------------------------


class InsightPoint(_Base):
    text: str
    citations: list[Citation] = Field(default_factory=list)


class CompareInsights(_Base):
    codes: list[str]
    points: list[InsightPoint]
    generated_by: str = Field(description="'llm:<provider>' or 'findings' (no LLM)")
