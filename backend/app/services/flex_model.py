"""Small scikit-learn models trained on FLEX Table IX (data/flex/flex_table_ix.csv).

- Burning-rate constant K (mm²/s): standardized ridge regression.
- Extinction probability: degree-2 logistic regression, trained on tests that ended in
  flame extinction vs. burning to completion (tests ended by droplet disruption say
  nothing about extinction and are excluded).

Training takes milliseconds on ~270 rows, so models are fit once per process on
first use. Metrics are 5-fold cross-validated and exposed to the UI.
"""

from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.model_selection import KFold, StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler

from app.config import DATA_DIR

MODEL_NAME = "flex-ridge-logit-v1"
FEATURES = ["heptane", "oxygen_percent", "pressure_kpa", "initial_diameter_mm", "co2_percent",
            "he_percent"]  # fmt: skip
CSV_PATH = DATA_DIR / "flex" / "flex_table_ix.csv"


@dataclass
class FlexModel:
    k_model: Pipeline
    ext_model: Pipeline
    n_k: int
    n_ext: int
    k_r2: float
    k_mae: float
    ext_auc: float
    ext_balanced_accuracy: float
    # Same cross-validation for naive baselines (mean K, majority class), to show the gain.
    k_mae_baseline: float = 0.0
    ext_bacc_baseline: float = 0.5
    ranges: dict[str, tuple[float, float]] = field(default_factory=dict)


def load_frame(path=CSV_PATH) -> pd.DataFrame:
    df = pd.read_csv(path)
    out = pd.DataFrame(
        {
            "heptane": (df["fuel"] == "n-heptane").astype(int),
            "oxygen_percent": df["o2_mole_fraction"] * 100,
            "pressure_kpa": df["pressure_atm"] * 101.325,
            "initial_diameter_mm": df["initial_diameter_mm"],
            "co2_percent": df["co2_mole_fraction"].fillna(0) * 100,
            "he_percent": df["he_mole_fraction"].fillna(0) * 100,
            "burn_rate_k": df["burn_rate_k_mm2_s"],
            "outcome": df["outcome"],
        }
    )
    return out.dropna(subset=FEATURES)


def train(df: pd.DataFrame) -> FlexModel:
    k_df = df.dropna(subset=["burn_rate_k"])
    xk, yk = k_df[FEATURES], k_df["burn_rate_k"]
    k_model = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
    kcv = KFold(5, shuffle=True, random_state=0)
    k_r2 = cross_val_score(k_model, xk, yk, cv=kcv, scoring="r2").mean()
    k_mae = -cross_val_score(k_model, xk, yk, cv=kcv, scoring="neg_mean_absolute_error").mean()
    k_model.fit(xk, yk)
    k_mae_base = -cross_val_score(
        DummyRegressor(strategy="mean"), xk, yk, cv=kcv, scoring="neg_mean_absolute_error"
    ).mean()

    e_df = df[df["outcome"].isin(["extinction", "complete_burn"])]
    xe, ye = e_df[FEATURES], (e_df["outcome"] == "extinction").astype(int)
    ext_model = make_pipeline(
        StandardScaler(),
        PolynomialFeatures(2),
        LogisticRegression(C=0.5, class_weight="balanced", max_iter=2000),
    )
    ecv = StratifiedKFold(5, shuffle=True, random_state=0)
    auc = cross_val_score(ext_model, xe, ye, cv=ecv, scoring="roc_auc").mean()
    bacc = cross_val_score(ext_model, xe, ye, cv=ecv, scoring="balanced_accuracy").mean()
    ext_model.fit(xe, ye)
    bacc_base = cross_val_score(
        DummyClassifier(strategy="most_frequent"), xe, ye, cv=ecv, scoring="balanced_accuracy"
    ).mean()

    ranges = {f: (float(df[f].min()), float(df[f].max())) for f in FEATURES if f != "heptane"}
    return FlexModel(
        k_model, ext_model, len(k_df), len(e_df),
        round(float(k_r2), 3), round(float(k_mae), 3),
        round(float(auc), 3), round(float(bacc), 3),
        round(float(k_mae_base), 3), round(float(bacc_base), 3), ranges,
    )  # fmt: skip


@lru_cache
def get_model() -> FlexModel | None:
    """The trained model, or None when the FLEX CSV is missing or empty."""
    if not CSV_PATH.exists():
        return None
    df = load_frame()
    if len(df) < 30:
        return None
    return train(df)


def features_row(
    fuel: str, oxygen_percent: float, pressure_kpa: float, initial_diameter_mm: float,
    co2_percent: float = 0.0, he_percent: float = 0.0,
) -> pd.DataFrame:  # fmt: skip
    heptane = 1 if "heptane" in fuel.lower() else 0
    return pd.DataFrame(
        [[heptane, oxygen_percent, pressure_kpa, initial_diameter_mm, co2_percent, he_percent]],
        columns=FEATURES,
    )


FLEX_PDF = "https://ntrs.nasa.gov/api/citations/20150023456/downloads/20150023456.pdf"


@lru_cache
def _tests() -> pd.DataFrame:
    """Every Table IX test with its features and what actually happened on the ISS."""
    raw = pd.read_csv(CSV_PATH)
    feats = load_frame()
    return feats.join(raw[["test_id", "extinction_diameter_mm", "source_page"]])


def nearest_test(x: pd.DataFrame) -> dict | None:
    """The real FLEX test closest to the inputs: same fuel, other features scaled by spread."""
    if not CSV_PATH.exists():
        return None
    df = _tests()
    row = x.iloc[0]
    same = df[df["heptane"] == row["heptane"]]
    if same.empty:
        return None
    cols = [f for f in FEATURES if f != "heptane"]
    spread = df[cols].std().replace(0, 1)
    dist = (((same[cols] - row[cols]) / spread) ** 2).sum(axis=1) ** 0.5
    best = same.loc[dist.idxmin()]
    ext = best["extinction_diameter_mm"]
    page = int(best["source_page"]) if pd.notna(best["source_page"]) else None
    return {
        "test_id": str(best["test_id"]),
        "fuel": "n-heptane" if best["heptane"] else "methanol",
        "oxygen_percent": round(float(best["oxygen_percent"]), 1),
        "pressure_kpa": round(float(best["pressure_kpa"]), 1),
        "initial_diameter_mm": round(float(best["initial_diameter_mm"]), 2),
        "co2_percent": round(float(best["co2_percent"]), 1),
        "he_percent": round(float(best["he_percent"]), 1),
        "outcome": str(best["outcome"]),
        "burn_rate_k": None
        if pd.isna(best["burn_rate_k"])
        else round(float(best["burn_rate_k"]), 3),
        "extinction_diameter_mm": None if pd.isna(ext) or ext <= 0 else round(float(ext), 2),
        "distance": round(float(dist.min()), 2),
        "source_page": page,
        "url": f"{FLEX_PDF}#page={page}" if page else FLEX_PDF,
    }


LABELS = {
    "oxygen_percent": ("Oxygen", "% O₂"),
    "pressure_kpa": ("Pressure", "kPa"),
    "initial_diameter_mm": ("Initial diameter", "mm"),
    "co2_percent": ("CO₂", "% CO₂"),
    "he_percent": ("Helium", "% He"),
}


def range_warnings(model: FlexModel, x: pd.DataFrame, fuel: str) -> list[str]:
    """One plain-English warning per input outside what the FLEX tests covered."""
    out = []
    if fuel.strip().lower() not in {"n-heptane", "heptane", "methanol"}:
        out.append(f"Fuel '{fuel}' was not tested in FLEX (only n-heptane and methanol).")
    row = x.iloc[0]
    for f, (lo, hi) in model.ranges.items():
        if not lo <= row[f] <= hi:
            name, unit = LABELS.get(f, (f, ""))
            out.append(
                f"{name} {row[f]:g} {unit} is outside the FLEX tests ({lo:.3g} to {hi:.3g} {unit})."
            )
    return out


def predict(model: FlexModel, x: pd.DataFrame) -> tuple[float, float, bool]:
    """Return (burn_rate_k, extinction_probability, inputs within training ranges)."""
    k = float(np.clip(model.k_model.predict(x)[0], 0.0, None))
    p = float(model.ext_model.predict_proba(x)[0, 1])
    row = x.iloc[0]
    in_range = all(lo <= row[f] <= hi for f, (lo, hi) in model.ranges.items())
    return round(k, 4), round(p, 4), in_range
