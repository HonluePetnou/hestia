"""Contrôle la transcription de la Table IX de FLEX et la compare aux données PSI.

Lancer depuis le dossier backend :
    uv run python -m pipeline.check_flex_table_ix

Entrées : data/flex/flex_table_ix.csv    (transcription manuelle de la Table IX)
          data/flex/flex_psi_clean.csv   (tableau PSI nettoyé par clean_flex.py)

Le script fait deux choses :
  1. il vérifie la transcription (valeurs permises, unités plausibles, somme des gaz) ;
  2. il cherche chaque essai de la Table IX dans les données PSI (même carburant, même
     pression, même oxygène, même diamètre) et compare K et le résultat.
"""

from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# 1. Les chemins et les réglages
# ---------------------------------------------------------------------------
RACINE = Path(__file__).resolve().parents[2]  # le dossier "hestia"
TABLE_IX = RACINE / "data" / "flex" / "flex_table_ix.csv"
PSI = RACINE / "data" / "flex" / "flex_psi_clean.csv"

RESULTATS_PERMIS = {"extinction", "disruption", "complete_burn", "unknown"}
# Plages plausibles : une valeur en dehors est probablement une faute de frappe.
PLAGES = {
    "pressure_atm": (0.3, 3.5),
    "o2_mole_fraction": (0.0, 1.0),
    "co2_mole_fraction": (0.0, 1.0),
    "n2_mole_fraction": (0.0, 1.0),
    "initial_diameter_mm": (0.5, 6.0),
    "burn_rate_k_mm2_s": (0.0, 2.0),
}
# Écart toléré pour considérer que deux essais ont les mêmes conditions.
TOLERANCES = {
    "pressure_atm": 0.02,
    "o2_mole_fraction": 0.005,
    "initial_diameter_mm": 0.05,
}
TOLERANCE_K = 0.02  # écart toléré sur K (mm²/s)

problemes = []  # la liste des points à vérifier

# ---------------------------------------------------------------------------
# 2. Lecture
# ---------------------------------------------------------------------------
if not TABLE_IX.exists():
    raise SystemExit(f"Fichier introuvable : {TABLE_IX}")
table = pd.read_csv(TABLE_IX)
print(f"Table IX transcrite : {len(table)} lignes")
if table.empty:
    raise SystemExit("La Table IX est vide : transcris quelques lignes puis relance.")

# ---------------------------------------------------------------------------
# 3. Contrôle de la transcription
# ---------------------------------------------------------------------------
mauvais = table[~table["outcome"].isin(RESULTATS_PERMIS)]
for _, ligne in mauvais.iterrows():
    problemes.append(f"{ligne['test_id']} : outcome « {ligne['outcome']} » non permis")

for colonne, (mini, maxi) in PLAGES.items():
    hors = table[(table[colonne] < mini) | (table[colonne] > maxi)]
    for _, ligne in hors.iterrows():
        problemes.append(
            f"{ligne['test_id']} : {colonne} = {ligne[colonne]} hors de [{mini}, {maxi}]"
        )

# Le guide 02 ne compte pas l'hélium : un essai avec hélium aura une somme inférieure à 1.
gaz = ["o2_mole_fraction", "co2_mole_fraction", "n2_mole_fraction"]
somme = table[gaz].fillna(0).sum(axis=1)
for i in table.index[(somme < 0.9) | (somme > 1.01)]:
    problemes.append(f"{table.loc[i, 'test_id']} : somme des gaz = {somme[i]:.2f} (hélium ?)")

for i in table.index[table["test_id"].duplicated(keep=False)]:
    problemes.append(f"{table.loc[i, 'test_id']} : identifiant en double")

# ---------------------------------------------------------------------------
# 4. Comparaison avec les données PSI
# ---------------------------------------------------------------------------
if not PSI.exists():
    print(f"\nComparaison impossible : {PSI.name} est absent (lance clean_flex d'abord).")
    psi = None
else:
    psi = pd.read_csv(PSI)

trouves = 0
k_identiques = 0
resultats_identiques = 0
absents = []
if psi is not None:
    for _, essai in table.iterrows():
        candidats = psi[psi["fuel"] == essai["fuel"]]
        for colonne, tolerance in TOLERANCES.items():
            candidats = candidats[(candidats[colonne] - essai[colonne]).abs() <= tolerance]
        if candidats.empty:
            absents.append(essai["test_id"])
            continue
        trouves += 1
        k_ok = candidats["burn_rate_k_mm2_s"].sub(essai["burn_rate_k_mm2_s"]).abs().le(TOLERANCE_K)
        k_identiques += int(k_ok.any() or pd.isna(essai["burn_rate_k_mm2_s"]))
        resultats_identiques += int((candidats["outcome"] == essai["outcome"]).any())

# ---------------------------------------------------------------------------
# 5. Compte rendu
# ---------------------------------------------------------------------------
print(f"\nPoints à vérifier dans la transcription : {len(problemes)}")
for p in problemes:
    print("  -", p)
if psi is not None:
    print("\nComparaison avec PSI (mêmes conditions d'essai) :")
    print(f"  essais retrouvés dans PSI : {trouves} sur {len(table)}")
    print(f"  K identique (à {TOLERANCE_K} près) : {k_identiques} sur {trouves}")
    print(f"  résultat identique        : {resultats_identiques} sur {trouves}")
    if absents:
        print("  non retrouvés :", ", ".join(map(str, absents[:20])))
