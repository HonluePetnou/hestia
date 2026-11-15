"""Nettoyage du tableau d'essais BASS téléchargé sur PSI (investigation PSI-26).

Ce tableau ne décrit que l'identification des essais (date, numéros, matériau) :
il ne contient aucune condition d'essai (oxygène, écoulement).

Lancer depuis le dossier backend :
    uv run python -m pipeline.clean_bass

Entrée  : data/psi/BASS/test_matrix.csv   (fichier brut, jamais modifié)
Sorties : data/bass/bass_clean.csv        (tableau propre)
          data/bass/bass_alertes.csv      (points à vérifier à la main)
"""

from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# 1. Les chemins des fichiers
# ---------------------------------------------------------------------------
RACINE = Path(__file__).resolve().parents[2]  # le dossier "hestia"
ENTREE = RACINE / "data" / "psi" / "BASS" / "test_matrix.csv"
SORTIE = RACINE / "data" / "bass" / "bass_clean.csv"
ALERTES = RACINE / "data" / "bass" / "bass_alertes.csv"

# ---------------------------------------------------------------------------
# 2. Les réglages
# ---------------------------------------------------------------------------
PSI_ID = "PSI-26"
DOI = "10.60555/58h4-dy80"
ANNEES_POSSIBLES = range(2012, 2019)  # BASS a volé entre 2012 et 2014 environ

# Les colonnes sont renommées par POSITION.
NOUVEAUX_NOMS = [
    "test_date",
    "gmt_day_of_year",
    "as_run_number",
    "test_id",
    "sample_id",
    "material_raw",
]
ORDRE_FINAL = [
    "experiment_code",
    "as_run_number",
    "test_id",
    "test_date",
    "gmt_day_of_year",
    "sample_id",
    "material_raw",
    "material_family",
    "shape",
    "size_cm",
    "flow_note",
    "is_test_run",
    "gravity",
    "source_psi",
    "source_doi",
]

# Mots cherchés dans la description du matériau (on ne devine rien d'autre).
FAMILLES = [
    ("pmma", "PMMA"),
    ("sibal", "SIBAL"),
    ("nomex", "Nomex"),
    ("ultem", "Ultem"),
    ("wax", "Wax"),
    ("paraffin", "Wax"),
    ("parrafin", "Wax"),  # faute de frappe présente dans le fichier
]
FORMES = [
    ("sphere", "sphere"),
    ("slab", "slab"),
    ("sheet", "sheet"),
    ("candle", "candle"),
]
NOTES_ECOULEMENT = [("wake", "wake"), ("opposed", "opposed"), ("oppsed", "opposed")]

alertes = []  # la liste des points à vérifier


def noter(ligne, colonne, probleme, action):
    """Ajoute une ligne dans la liste des alertes."""
    alertes.append(
        {
            "as_run_number": df.loc[ligne, "as_run_number"],
            "test_id": df.loc[ligne, "test_id"],
            "colonne": colonne,
            "probleme": probleme,
            "action": action,
        }
    )


def chercher(texte, liste):
    """Renvoie le premier nom dont le mot-clé apparaît dans le texte."""
    t = str(texte).lower()
    for mot, nom in liste:
        if mot in t:
            return nom
    return None


# ---------------------------------------------------------------------------
# 3. Lecture du fichier brut
# ---------------------------------------------------------------------------
df = pd.read_csv(ENTREE, encoding="utf-8-sig", dtype=str)
assert len(df.columns) == len(NOUVEAUX_NOMS), "nombre de colonnes inattendu"
df.columns = NOUVEAUX_NOMS
lignes_brutes = len(df)
for colonne in df.columns:
    df[colonne] = df[colonne].str.replace(r"\s+", " ", regex=True).str.strip()

# ---------------------------------------------------------------------------
# 4. Numéros et matériau
# ---------------------------------------------------------------------------
df["as_run_number"] = pd.to_numeric(df["as_run_number"], errors="coerce").astype("Int64")
df["is_test_run"] = df["test_id"].notna()  # « SOOT Cleaning » n'est pas un essai
df["material_family"] = df["material_raw"].map(lambda t: chercher(t, FAMILLES))
df["shape"] = df["material_raw"].map(lambda t: chercher(t, FORMES))
df["flow_note"] = df["material_raw"].map(lambda t: chercher(t, NOTES_ECOULEMENT))
# Dimension écrite « 2 cm » ou « 1 cm » dans la description (diamètre ou largeur).
df["size_cm"] = df["material_raw"].str.extract(r"(\d+(?:\.\d+)?) cm", expand=False)
df["size_cm"] = pd.to_numeric(df["size_cm"])

# ---------------------------------------------------------------------------
# 5. Dates
# ---------------------------------------------------------------------------
# Mois/jour/année. Le jour GMT est le numéro du jour dans l'année.
date_brute = df["test_date"]
propre = date_brute.str.replace("`", "", regex=False)  # « 6/29/`12 » : erreur de frappe
dates = pd.to_datetime(propre, format="%m/%d/%Y", errors="coerce")
dates = dates.fillna(pd.to_datetime(propre, format="%m/%d/%y", errors="coerce"))
for i in df.index[propre != date_brute]:
    noter(
        i,
        "test_date",
        f"date « {date_brute[i]} » lue comme {dates[i]:%Y-%m-%d}",
        "corrigée",
    )
for i in df.index[dates.isna()]:
    noter(i, "test_date", f"date illisible « {date_brute[i]} »", "mise à vide")
impossible = dates.notna() & ~dates.dt.year.isin(ANNEES_POSSIBLES)
for i in df.index[impossible]:
    noter(i, "test_date", f"année impossible dans « {date_brute[i]} »", "mise à vide")
dates = dates.where(~impossible)
df["test_date"] = dates.dt.strftime("%Y-%m-%d")
df["gmt_day_of_year"] = pd.to_numeric(df["gmt_day_of_year"], errors="coerce").astype("Int64")
ecart = (df["gmt_day_of_year"] != dates.dt.day_of_year) & dates.notna()
for i in df.index[ecart.fillna(False)]:
    noter(
        i,
        "gmt_day_of_year",
        f"jour GMT {df.loc[i, 'gmt_day_of_year']} ≠ date",
        "à vérifier",
    )

# ---------------------------------------------------------------------------
# 6. Contrôles qui ne modifient rien : on signale seulement
# ---------------------------------------------------------------------------
vrais = df[df["is_test_run"]]
for colonne in ["as_run_number", "test_id"]:
    doublons = vrais[colonne].duplicated(keep=False) & vrais[colonne].notna()
    for i in vrais.index[doublons]:
        noter(i, colonne, f"valeur « {df.loc[i, colonne]} » en double", "à vérifier")

# ---------------------------------------------------------------------------
# 7. Gravité, source et sauvegarde
# ---------------------------------------------------------------------------
df["experiment_code"] = "BASS"
df["gravity"] = "microgravity"  # BASS a été réalisé sur l'ISS
df["source_psi"] = PSI_ID
df["source_doi"] = DOI

SORTIE.parent.mkdir(parents=True, exist_ok=True)
df[ORDRE_FINAL].to_csv(SORTIE, index=False, encoding="utf-8")
colonnes_alertes = ["as_run_number", "test_id", "colonne", "probleme", "action"]
pd.DataFrame(alertes, columns=colonnes_alertes).to_csv(ALERTES, index=False, encoding="utf-8")

# ---------------------------------------------------------------------------
# 8. Petit compte rendu à l'écran
# ---------------------------------------------------------------------------
print(f"Lignes lues         : {lignes_brutes} (dont {int(df['is_test_run'].sum())} essais)")
print(f"Alertes             : {len(alertes)} (voir {ALERTES.name})")
print("Matériaux           :", df["material_family"].value_counts(dropna=False).to_dict())
print("Formes              :", df["shape"].value_counts(dropna=False).to_dict())
print(f"Fichier propre      : {SORTIE}")
