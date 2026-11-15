"""/predict and /predict/model behaviour (adapted from kikat234's feat/flex-ml tests)."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import flex_model

client = TestClient(app)
trained = pytest.mark.skipif(flex_model.get_model() is None, reason="FLEX CSV not available")

IN_RANGE = {
    "fuel": "n-heptane",
    "oxygen_percent": 21,
    "pressure_kpa": 101.3,
    "initial_diameter_mm": 3.0,
    "co2_percent": 0,
}


@trained
def test_in_range_prediction_has_no_warnings() -> None:
    data = client.post("/predict", json=IN_RANGE).json()
    assert data["burn_rate_k"] > 0
    assert 0.0 <= data["extinction_probability"] <= 1.0
    assert abs(data["droplet_lifetime_s"] - 9.0 / data["burn_rate_k"]) < 0.05
    assert data["in_training_range"] is True
    assert data["warnings"] == []


@trained
def test_out_of_range_inputs_get_one_warning_each() -> None:
    payload = {**IN_RANGE, "fuel": "kerosene", "oxygen_percent": 74}
    data = client.post("/predict", json=payload).json()
    assert data["in_training_range"] is False
    joined = " ".join(data["warnings"])
    assert "kerosene" in joined and "Oxygen 74" in joined
    assert len(data["warnings"]) == 2


def test_invalid_inputs_are_rejected() -> None:
    bad = {**IN_RANGE, "oxygen_percent": 150, "pressure_kpa": -1}
    assert client.post("/predict", json=bad).status_code == 422


def test_mock_fallback_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(flex_model, "get_model", lambda: None)
    data = client.post("/predict", json=IN_RANGE).json()
    assert data["model"] == "mock"
    assert data["in_training_range"] is False
    assert data["warnings"]


@trained
def test_model_beats_naive_baselines() -> None:
    info = client.get("/predict/model").json()
    assert info["k_mae_cv"] < info["k_mae_baseline_cv"]
    assert (
        info["extinction_balanced_accuracy_cv"] > info["extinction_balanced_accuracy_baseline_cv"]
    )
