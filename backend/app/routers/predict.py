from pathlib import Path

import joblib
import pandas as pd
from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(tags=["predict"])

MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "flex_k.joblib"
_BUNDLE = joblib.load(MODEL_PATH) if MODEL_PATH.exists() else None


class PredictRequest(BaseModel):
    fuel: str = Field(..., examples=["n-heptane"])
    pressure_atm: float = Field(..., gt=0, examples=[1.0])
    o2_mole_fraction: float = Field(..., ge=0, le=1, examples=[0.21])
    co2_mole_fraction: float = Field(0.0, ge=0, le=1, examples=[0.0])
    initial_diameter_mm: float = Field(..., gt=0, examples=[3.0])


class PredictResponse(BaseModel):
    burn_rate_k: float
    extinction_probability: float
    burn_time_s: float
    model: str
    mae_mm2_s: float | None = None
    out_of_range: bool
    warnings: list[str]


def check_out_of_range(req: PredictRequest, bounds: dict) -> list[str]:
    warnings: list[str] = []
    fuel_clean = req.fuel.strip().lower()
    if fuel_clean not in bounds["fuels"]:
        warnings.append(
            f"Carburant '{req.fuel}' absent des essais FLEX ({', '.join(bounds['fuels'])})."
        )
    for field_name, limits in bounds["numeric"].items():
        val = getattr(req, field_name)
        if val < limits["min"] or val > limits["max"]:
            warnings.append(
                f"{field_name}={val} hors plage FLEX [{limits['min']:.3f}, {limits['max']:.3f}]."
            )
    return warnings


@router.post("/predict", response_model=PredictResponse)
def predict_droplet(req: PredictRequest) -> PredictResponse:
    if _BUNDLE is None:
        k_mock = 0.60
        return PredictResponse(
            burn_rate_k=k_mock,
            extinction_probability=0.25,
            burn_time_s=round((req.initial_diameter_mm**2) / k_mock, 2),
            model="mock-fallback",
            mae_mm2_s=None,
            out_of_range=True,
            warnings=["Modèle ML non chargé : valeurs de repli affichées."],
        )

    warnings = check_out_of_range(req, _BUNDLE["bounds"])
    input_df = pd.DataFrame(
        [
            {
                "fuel": req.fuel.strip().lower(),
                "pressure_atm": req.pressure_atm,
                "o2_mole_fraction": req.o2_mole_fraction,
                "co2_mole_fraction": req.co2_mole_fraction,
                "initial_diameter_mm": req.initial_diameter_mm,
            }
        ]
    )

    k_pred = float(_BUNDLE["reg_pipeline"].predict(input_df)[0])
    k_pred = max(k_pred, 0.01)  # Avoid any division by zero on d0² / K
    ext_prob = float(_BUNDLE["clf_pipeline"].predict_proba(input_df)[0][1])
    burn_time = (req.initial_diameter_mm**2) / k_pred
    mae = _BUNDLE["metrics"]["reg"]["forest_reg"]["mae_mean"]

    return PredictResponse(
        burn_rate_k=round(k_pred, 4),
        extinction_probability=round(ext_prob, 4),
        burn_time_s=round(burn_time, 2),
        model=_BUNDLE["version"],
        mae_mm2_s=round(mae, 3),
        out_of_range=len(warnings) > 0,
        warnings=warnings,
    )
