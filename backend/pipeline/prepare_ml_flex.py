"""Prépare les données FLEX nettoyées pour le modèle de prédiction (guide 05).

Lancer depuis le dossier backend :
    uv run python -m pipeline.prepare_ml_flex

Entrée  : data/flex/flex_psi_clean.csv      (tableau nettoyé par clean_flex.py)
Sorties : data/flex/flex_ml_ready.csv       (une ligne par essai utilisable)
          data/flex/flex_ml_ranges.json     (plages et effectifs pour la fiche du modèle)

Le script ne garde que les colonnes connues AVANT l'essai. Les colonnes mesurées pendant
ou après l'essai (durée de combustion, diamètre à l'extinction) sont exclues : les utiliser
pour prédire le résultat serait une fuite d'information.
"""

import json
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# 1. Les chemins et les réglages
# ---------------------------------------------------------------------------
RACINE = Path(__file__).resolve().parents[2]  # le dossier "hestia"
ENTREE = RACINE / "data" / "flex" / "flex_psi_clean.csv"
SORTIE = RACINE / "data" / "flex" / "flex_ml_ready.csv"
PLAGES = RACINE / "data" / "flex" / "flex_ml_ranges.json"

ENTREES_NOMBRES = [
    "pressure_atm",
    "o2_mole_fraction",
    "co2_mole_fraction",
    "he_mole_fraction",
    "initial_diameter_mm",
]
EXCLUES = {
    "burn_time_s": "mesurée pendant l'essai : vaut à peu près d0² / K (fuite d'information)",
    "extinction_diameter_mm": "mesuré pendant l'essai (fuite d'information)",
    "test_number": "numéro d'ordre, sans lien physique avec le résultat",
    "test_date": "date de l'essai, sans lien physique avec le résultat",
    "test_gmt": "heure de l'essai, sans lien physique avec le résultat",
}

# ---------------------------------------------------------------------------
# 2. Lecture et sélection des lignes utilisables
# ---------------------------------------------------------------------------
df = pd.read_csv(ENTREE)
total = len(df)

# Une ligne est utilisable si le carburant et toutes les entrées sont connus.
complet = df.dropna(subset=["fuel", *ENTREES_NOMBRES]).copy()
complet["extinction"] = (complet["outcome"] == "extinction").astype(int)
complet["usable_for_regression"] = complet["burn_rate_k_mm2_s"].notna()
complet["usable_for_classification"] = complet["outcome"] != "unknown"

colonnes = ["test_id", "fuel", *ENTREES_NOMBRES]
colonnes += ["burn_rate_k_mm2_s", "extinction", "outcome"]
colonnes += ["usable_for_regression", "usable_for_classification"]
prets = complet[colonnes]

# ---------------------------------------------------------------------------
# 3. Plages et effectifs (pour la fiche du modèle et pour signaler « hors plage »)
# ---------------------------------------------------------------------------
reg = prets[prets["usable_for_regression"]]
cla = prets[prets["usable_for_classification"]]
resume = {
    "source": "data/flex/flex_psi_clean.csv (PSI-69, DOI 10.60555/mbq8-0451)",
    "rows_total": int(total),
    "rows_with_complete_inputs": len(prets),
    "rows_for_regression": len(reg),
    "rows_for_classification": len(cla),
    "extinction_yes": int((cla["extinction"] == 1).sum()),
    "extinction_no": int((cla["extinction"] == 0).sum()),
    "fuels": prets["fuel"].value_counts().to_dict(),
    "input_ranges": {c: [float(prets[c].min()), float(prets[c].max())] for c in ENTREES_NOMBRES},
    "k_mm2_s": {
        "min": float(reg["burn_rate_k_mm2_s"].min()),
        "max": float(reg["burn_rate_k_mm2_s"].max()),
        "mean": round(float(reg["burn_rate_k_mm2_s"].mean()), 4),
    },
    "excluded_columns": EXCLUES,
    "limits": "microgravité ISS uniquement ; pas de gravité lunaire ni martienne ; "
    "carburants testés seulement",
}

# ---------------------------------------------------------------------------
# 4. Sauvegarde et compte rendu
# ---------------------------------------------------------------------------
prets.to_csv(SORTIE, index=False, encoding="utf-8")
with open(PLAGES, "w", encoding="utf-8") as f:
    json.dump(resume, f, ensure_ascii=False, indent=2)
    f.write("\n")

print(f"Essais au total              : {total}")
print(f"Entrées complètes            : {len(prets)}")
print(f"Utilisables (régression K)   : {len(reg)}")
print(f"Utilisables (classification) : {len(cla)}")
print(f"Extinction oui / non         : {resume['extinction_yes']} / {resume['extinction_no']}")
for colonne, (mini, maxi) in resume["input_ranges"].items():
    print(f"  {colonne:22s} de {mini:g} à {maxi:g}")
print(f"Fichiers écrits              : {SORTIE.name}, {PLAGES.name}")
