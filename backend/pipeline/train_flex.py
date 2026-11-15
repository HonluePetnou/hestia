from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import f1_score, make_scorer
from sklearn.model_selection import KFold, StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

DATA_PATH = Path("../data/flex/sample_test.csv")
MODEL_PATH = Path("models/flex_k.joblib")

FEATURES = [
    "fuel",
    "pressure_atm",
    "o2_mole_fraction",
    "co2_mole_fraction",
    "initial_diameter_mm",
]
NUMERIC_FEATURES = [
    "pressure_atm",
    "o2_mole_fraction",
    "co2_mole_fraction",
    "initial_diameter_mm",
]


def build_preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("fuel", OneHotEncoder(handle_unknown="ignore"), ["fuel"]),
            ("num", SimpleImputer(strategy="median"), NUMERIC_FEATURES),
        ]
    )


def main() -> None:
    df = pd.read_csv(DATA_PATH)
    df["fuel"] = df["fuel"].str.strip().str.lower()

    # 1. Calcul des plages d'entraînement pour la détection "hors plage"
    bounds = {
        "fuels": sorted(df["fuel"].dropna().unique().tolist()),
        "numeric": {
            col: {
                "min": float(df[col].min()),
                "max": float(df[col].max()),
            }
            for col in NUMERIC_FEATURES
        },
    }

    # 2. Régression de la constante K (burn_rate_k_mm2_s)
    df_reg = df.dropna(subset=["burn_rate_k_mm2_s"]).copy()
    X_reg = df_reg[FEATURES]
    y_reg = df_reg["burn_rate_k_mm2_s"]

    cv_reg = KFold(n_splits=5, shuffle=True, random_state=42)
    reg_models = {
        "baseline_mean": DummyRegressor(strategy="mean"),
        "forest_reg": RandomForestRegressor(
            n_estimators=300, max_depth=5, min_samples_leaf=3, random_state=42
        ),
    }

    print(f"=== RÉGRESSION K (n={len(df_reg)}) ===")
    reg_scores = {}
    for name, model in reg_models.items():
        pipe = Pipeline([("prep", build_preprocessor()), ("model", model)])
        mae = -cross_val_score(pipe, X_reg, y_reg, cv=cv_reg, scoring="neg_mean_absolute_error")
        r2 = cross_val_score(pipe, X_reg, y_reg, cv=cv_reg, scoring="r2")
        reg_scores[name] = {"mae_mean": float(mae.mean()), "mae_std": float(mae.std())}
        print(f"{name:15s} | MAE: {mae.mean():.3f} ± {mae.std():.3f} mm²/s | R²: {r2.mean():.3f}")

    final_reg_pipe = Pipeline([("prep", build_preprocessor()), ("model", reg_models["forest_reg"])])
    final_reg_pipe.fit(X_reg, y_reg)

    # 3. Classification du risque d'extinction (outcome == "extinction")
    df_clf = df[df["outcome"].isin(["extinction", "disruption", "complete_burn"])].copy()
    X_clf = df_clf[FEATURES]
    y_clf = (df_clf["outcome"] == "extinction").astype(int)

    cv_clf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    clf_models = {
        "baseline_major": DummyClassifier(strategy="most_frequent"),
        "forest_clf": RandomForestClassifier(
            n_estimators=300, max_depth=5, min_samples_leaf=3, random_state=42
        ),
    }

    print(f"\n=== CLASSIFICATION EXTINCTION (n={len(df_clf)}) ===")
    clf_scores = {}
    for name, model in clf_models.items():
        pipe = Pipeline([("prep", build_preprocessor()), ("model", model)])
        f1 = cross_val_score(
            pipe, X_clf, y_clf, cv=cv_clf, scoring=make_scorer(f1_score, zero_division=0)
        )
        acc = cross_val_score(pipe, X_clf, y_clf, cv=cv_clf, scoring="accuracy")
        clf_scores[name] = {"f1_mean": float(f1.mean()), "acc_mean": float(acc.mean())}
        print(f"{name:15s} | F1: {f1.mean():.3f} ± {f1.std():.3f} | Accuracy: {acc.mean():.3f}")

    final_clf_pipe = Pipeline([("prep", build_preprocessor()), ("model", clf_models["forest_clf"])])
    final_clf_pipe.fit(X_clf, y_clf)

    # 4. Sauvegarde du bundle complet
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    bundle = {
        "version": "flex-rf-v1",
        "reg_pipeline": final_reg_pipe,
        "clf_pipeline": final_clf_pipe,
        "bounds": bounds,
        "metrics": {
            "n_reg": len(df_reg),
            "n_clf": len(df_clf),
            "reg": reg_scores,
            "clf": clf_scores,
        },
    }
    joblib.dump(bundle, MODEL_PATH)
    print(f"\nModèle sauvegardé dans {MODEL_PATH.resolve()}")
    print("Plages d'entraînement :", bounds)


if __name__ == "__main__":
    main()
