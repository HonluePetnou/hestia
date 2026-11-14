"""Nettoyage du tableau d'essais FLEX téléchargé sur PSI (investigation PSI-69).

Lancer depuis le dossier backend :
    uv run python -m pipeline.clean_flex

Entrée  : data/psi/FLEX/test_matrix.csv   (fichier brut, jamais modifié)
Sorties : data/flex/flex_psi_clean.csv    (tableau propre)
          data/flex/flex_psi_alertes.csv  (points à vérifier à la main)
"""

from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# 1. Les chemins des fichiers
# ---------------------------------------------------------------------------
RACINE = Path(__file__).resolve().parents[2]  # le dossier "hestia"
ENTREE = RACINE / "data" / "psi" / "FLEX" / "test_matrix.csv"
SORTIE = RACINE / "data" / "flex" / "flex_psi_clean.csv"
ALERTES = RACINE / "data" / "flex" / "flex_psi_alertes.csv"

# ---------------------------------------------------------------------------
# 2. Les réglages (tout ce qui est écrit en dur est ici, au même endroit)
# ---------------------------------------------------------------------------
PSI_ID = "PSI-69"
DOI = "10.60555/mbq8-0451"
MMHG_PAR_ATM = 760.0  # 1 atm = 760 mmHg
TIRETS = {"–", "—", "-"}  # signes utilisés par PSI pour dire "non renseigné"
TOLERANCE_GAZ = 0.015  # écart toléré entre la somme des gaz et 1 (arrondis)

NOUVEAUX_NOMS = {
    "FLEX Test #": "test_number",
    "FLEX Identifier": "test_id",
    "Test Date": "test_date",
    "Test GMT": "test_gmt",
    "Fuel": "fuel",
    "Ambient pressure; mmHg": "pressure_mmhg",
    "O initial ambient composition; mole fraction": "o2_mole_fraction",
    "N initial ambient composition; mole fraction": "n2_mole_fraction",
    "CO initial ambient composition; mole fraction": "co2_mole_fraction",
    "He initial ambient composition; mole fraction": "he_mole_fraction",
    "Droplet initial diameter; mm": "initial_diameter_mm",
    "Visible flame extinction diameter; mm": "extinction_diameter_mm",
    "Burning rate; mm": "burn_rate_k_mm2_s",
    "Burn time; s": "burn_time_s",
    "Test end": "outcome",
}
COLONNES_NOMBRES = [
    "test_number",
    "pressure_mmhg",
    "o2_mole_fraction",
    "n2_mole_fraction",
    "co2_mole_fraction",
    "he_mole_fraction",
    "initial_diameter_mm",
    "extinction_diameter_mm",
    "burn_rate_k_mm2_s",
    "burn_time_s",
]
CARBURANTS = {"Heptane": "n-heptane", "Methanol": "methanol"}  # à vérifier
RESULTATS = {
    "Extinction": "extinction",
    "Disruption": "disruption",
    "Completion": "complete_burn",
}
ORDRE_FINAL = [
    "test_number",
    "test_id",
    "test_date",
    "test_gmt",
    "fuel",
    "pressure_atm",
    "o2_mole_fraction",
    "co2_mole_fraction",
    "n2_mole_fraction",
    "he_mole_fraction",
    "initial_diameter_mm",
    "outcome",
    "burn_rate_k_mm2_s",
    "extinction_diameter_mm",
    "burn_time_s",
    "gravity",
    "source_psi",
    "source_doi",
]

alertes = []  # la liste des points à vérifier


def noter(ligne, colonne, probleme, action):
    """Ajoute une ligne dans la liste des alertes."""
    alertes.append(
        {
            "test_number": df.loc[ligne, "test_number"],
            "test_id": df.loc[ligne, "test_id"],
            "colonne": colonne,
            "probleme": probleme,
            "action": action,
        }
    )


# ---------------------------------------------------------------------------
# 3. Lecture du fichier brut
# ---------------------------------------------------------------------------
# encoding="cp1252" : le fichier est en Windows-1252, pas en UTF-8.
# dtype=str : on lit tout comme du texte pour voir les "–" et les "~6".
df = pd.read_csv(ENTREE, encoding="cp1252", dtype=str)
df.columns = df.columns.str.strip()
df = df.rename(columns=NOUVEAUX_NOMS)
lignes_brutes = len(df)

# ---------------------------------------------------------------------------
# 4. Texte -> nombres
# ---------------------------------------------------------------------------
n_tirets = 0
for colonne in COLONNES_NOMBRES:
    texte = df[colonne].str.strip()
    nombre = pd.to_numeric(texte, errors="coerce")
    illisible = nombre.isna() & texte.notna()
    for i in df.index[illisible]:
        if texte[i] in TIRETS:
            n_tirets += 1
        else:
            noter(i, colonne, f"valeur non numérique « {texte[i]} »", "mise à vide")
    df[colonne] = nombre
df["test_number"] = df["test_number"].astype("Int64")

# ---------------------------------------------------------------------------
# 5. Pression : mmHg -> atm
# ---------------------------------------------------------------------------
impossible = df["pressure_mmhg"] <= 0
for i in df.index[impossible]:
    noter(i, "pressure_mmhg", "pression de 0 mmHg (impossible)", "mise à vide")
df.loc[impossible, "pressure_mmhg"] = pd.NA
df["pressure_atm"] = (df["pressure_mmhg"] / MMHG_PAR_ATM).round(4)

# ---------------------------------------------------------------------------
# 6. Carburant, résultat, date, gravité, source
# ---------------------------------------------------------------------------
carburant_brut = df["fuel"].str.strip()
df["fuel"] = carburant_brut.map(CARBURANTS)
for i in df.index[df["fuel"].isna() & carburant_brut.notna()]:
    noter(i, "fuel", f"carburant inconnu « {carburant_brut[i]} »", "mise à vide")

resultat_brut = df["outcome"].str.strip()
df["outcome"] = resultat_brut.map(RESULTATS).fillna("unknown")

# Les dates sont écrites mois/jour/année : 3/5/2009 = 5 mars 2009.
# Certaines ont l'année sur 2 chiffres (10/24/09) : on essaie les deux formes.
date_brute = df["test_date"].str.strip()
dates = pd.to_datetime(date_brute, format="%m/%d/%Y", errors="coerce")
dates = dates.fillna(pd.to_datetime(date_brute, format="%m/%d/%y", errors="coerce"))
for i in df.index[dates.isna() & date_brute.notna()]:
    noter(i, "test_date", f"date illisible « {date_brute[i]} »", "mise à vide")
df["test_date"] = dates.dt.strftime("%Y-%m-%d")

df["gravity"] = "microgravity"  # FLEX a été réalisé sur l'ISS
df["source_psi"] = PSI_ID
df["source_doi"] = DOI

# ---------------------------------------------------------------------------
# 7. Contrôles qui ne modifient rien : on signale seulement
# ---------------------------------------------------------------------------
gaz = ["o2_mole_fraction", "n2_mole_fraction", "co2_mole_fraction", "he_mole_fraction"]
somme = df[gaz].sum(axis=1)
for i in df.index[(somme - 1).abs() > TOLERANCE_GAZ]:
    noter(i, "gaz", f"somme des fractions = {somme[i]:.2f} (attendu 1)", "à vérifier")

for i in df.index[df["test_id"].duplicated(keep=False)]:
    noter(i, "test_id", f"identifiant « {df.loc[i, 'test_id']} » en double", "à vérifier")

# ---------------------------------------------------------------------------
# 8. Sauvegarde
# ---------------------------------------------------------------------------
valeurs_permises = {"extinction", "disruption", "complete_burn", "unknown"}
assert df["outcome"].isin(valeurs_permises).all(), "résultat inattendu"

SORTIE.parent.mkdir(parents=True, exist_ok=True)
df[ORDRE_FINAL].to_csv(SORTIE, index=False, encoding="utf-8")
colonnes_alertes = ["test_number", "test_id", "colonne", "probleme", "action"]
pd.DataFrame(alertes, columns=colonnes_alertes).to_csv(ALERTES, index=False, encoding="utf-8")

# ---------------------------------------------------------------------------
# 9. Petit compte rendu à l'écran
# ---------------------------------------------------------------------------
print(f"Lignes lues         : {lignes_brutes}")
print(f"Tirets mis à vide   : {n_tirets}")
print(f"Alertes             : {len(alertes)} (voir {ALERTES.name})")
print(f"K renseigné         : {df['burn_rate_k_mm2_s'].notna().sum()} lignes")
print("Résultats           :", df["outcome"].value_counts().to_dict())
print(f"Fichier propre      : {SORTIE}")
