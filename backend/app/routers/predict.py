import math

from fastapi import APIRouter

from app.schemas import PredictRequest, PredictResponse

router = APIRouter(tags=["predict"])


@router.post("/predict", response_model=PredictResponse)
def predict(body: PredictRequest) -> PredictResponse:
    """Phase 1: deterministic MOCK formula, not physics.

    TODO(hackathon): replace with a scikit-learn model trained on data/flex/flex_table_ix.csv.
    """
    k = 0.5 + 0.01 * (body.oxygen_percent - 21) + 0.02 * body.initial_diameter_mm
    z = 0.15 * (16 - body.oxygen_percent) + 0.3 * (body.initial_diameter_mm - 3)
    return PredictResponse(
        burn_rate_k=round(max(k, 0.0), 4),
        extinction_probability=round(1 / (1 + math.exp(-z)), 4),
        model="mock",
    )
