import math

from fastapi import APIRouter

from app.schemas import ModelInfo, NearestTest, PredictRequest, PredictResponse
from app.services import flex_model

router = APIRouter(tags=["predict"])

SOURCE = "FLEX Table IX, NASA/TP-2015-216046 (NTRS 20150023456)"


@router.post("/predict", response_model=PredictResponse)
def predict(body: PredictRequest) -> PredictResponse:
    """Droplet burning rate and extinction probability from models trained on FLEX tests.

    Falls back to a clearly labelled mock formula when the FLEX CSV is missing.
    """
    model = flex_model.get_model()
    x = flex_model.features_row(
        body.fuel, body.oxygen_percent, body.pressure_kpa, body.initial_diameter_mm,
        body.co2_percent, body.he_percent,
    )  # fmt: skip
    nearest = flex_model.nearest_test(x)
    if model is None:
        k = max(0.5 + 0.01 * (body.oxygen_percent - 21) + 0.02 * body.initial_diameter_mm, 0.05)
        z = 0.15 * (16 - body.oxygen_percent) + 0.3 * (body.initial_diameter_mm - 3)
        p, in_range, name = 1 / (1 + math.exp(-z)), False, "mock"
        warnings = ["FLEX data missing: these numbers come from a placeholder formula."]
    else:
        k, p, in_range = flex_model.predict(model, x)
        warnings = flex_model.range_warnings(model, x, body.fuel)
        name = flex_model.MODEL_NAME
    lifetime = body.initial_diameter_mm**2 / k if k > 0 else 0.0
    return PredictResponse(
        burn_rate_k=round(k, 4),
        extinction_probability=round(p, 4),
        droplet_lifetime_s=round(lifetime, 2),
        in_training_range=in_range,
        model=name,
        warnings=warnings,
        nearest_test=NearestTest(**nearest) if nearest else None,
    )


@router.get("/predict/model", response_model=ModelInfo)
def model_info() -> ModelInfo:
    """Training size, cross-validated metrics and valid input ranges of the model."""
    m = flex_model.get_model()
    if m is None:
        return ModelInfo(model="mock", trained=False, source=SOURCE)
    return ModelInfo(
        model=flex_model.MODEL_NAME,
        trained=True,
        source=SOURCE,
        k_samples=m.n_k,
        extinction_samples=m.n_ext,
        k_r2_cv=m.k_r2,
        k_mae_cv=m.k_mae,
        extinction_auc_cv=m.ext_auc,
        extinction_balanced_accuracy_cv=m.ext_balanced_accuracy,
        k_mae_baseline_cv=m.k_mae_baseline,
        extinction_balanced_accuracy_baseline_cv=m.ext_bacc_baseline,
        ranges=m.ranges,
    )
