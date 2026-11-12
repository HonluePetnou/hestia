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

    ranges = {f: (float(df[f].min()), float(df[f].max())) for f in FEATURES if f != "heptane"}
    return FlexModel(
        k_model, ext_model, len(k_df), len(e_df),
        round(float(k_r2), 3), round(float(k_mae), 3),
        round(float(auc), 3), round(float(bacc), 3), ranges,
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


def predict(model: FlexModel, x: pd.DataFrame) -> tuple[float, float, bool]:
    """Return (burn_rate_k, extinction_probability, inputs within training ranges)."""
    k = float(np.clip(model.k_model.predict(x)[0], 0.0, None))
    p = float(model.ext_model.predict_proba(x)[0, 1])
    row = x.iloc[0]
    in_range = all(lo <= row[f] <= hi for f, (lo, hi) in model.ranges.items())
    return round(k, 4), round(p, 4), in_range
