import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import predict as predict_router

client = TestClient(app)


def test_predict_in_range() -> None:
    """Verify standard FLEX experimental inputs return valid combustion metrics."""
    payload = {
        "fuel": "n-heptane",
        "pressure_atm": 1.0,
        "o2_mole_fraction": 0.21,
        "co2_mole_fraction": 0.0,
        "initial_diameter_mm": 3.0,
    }
    response = client.post("/predict", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["burn_rate_k"] > 0
    assert 0.0 <= data["extinction_probability"] <= 1.0
    assert abs(data["burn_time_s"] - (9.0 / data["burn_rate_k"])) < 0.05

    if predict_router._BUNDLE is not None:
        assert data["model"] != "mock-fallback"
        assert data["mae_mm2_s"] is not None
        assert data["out_of_range"] is False
        assert data["warnings"] == []


def test_predict_out_of_range_warnings() -> None:
    """Verify extrapolation flags out_of_range=True and populates warnings."""
    payload = {
        "fuel": "kerosene",
        "pressure_atm": 1.01,
        "o2_mole_fraction": 0.74,
        "co2_mole_fraction": 0.0,
        "initial_diameter_mm": 3.0,
    }
    response = client.post("/predict", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["burn_rate_k"] > 0
    assert data["burn_time_s"] > 0
    assert data["out_of_range"] is True
    assert len(data["warnings"]) >= 1


def test_predict_validation_error() -> None:
    """Verify Pydantic rejects physically invalid input ranges with HTTP 422."""
    invalid_payload = {
        "fuel": "n-heptane",
        "pressure_atm": -1.0,
        "o2_mole_fraction": 1.5,
        "co2_mole_fraction": 0.0,
        "initial_diameter_mm": 3.0,
    }
    response = client.post("/predict", json=invalid_payload)
    assert response.status_code == 422


def test_predict_mock_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify safe fallback response when the joblib model bundle is unavailable."""
    monkeypatch.setattr(predict_router, "_BUNDLE", None)

    payload = {
        "fuel": "n-heptane",
        "pressure_atm": 1.0,
        "o2_mole_fraction": 0.21,
        "co2_mole_fraction": 0.0,
        "initial_diameter_mm": 3.0,
    }
    response = client.post("/predict", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["model"] == "mock-fallback"
    assert data["mae_mm2_s"] is None
    assert data["out_of_range"] is True
    assert data["burn_time_s"] == 15.0
