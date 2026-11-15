"""Nettoyage du tableau d'essais BASS-II téléchargé sur PSI (investigation PSI-25).

Lancer depuis le dossier backend :
    uv run python -m pipeline.clean_bass2

Entrée  : data/psi/BASS-II/test_matrix.csv   (fichier brut, jamais modifié)
Sorties : data/bass/bass2_clean.csv          (tableau propre)
          data/bass/bass2_alertes.csv        (points à vérifier à la main)
"""

from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# 1. Les chemins des fichiers
# ---------------------------------------------------------------------------
RACINE = Path(__file__).resolve().parents[2]  # le dossier "hestia"
ENTREE = RACINE / "data" / "psi" / "BASS-II" / "test_matrix.csv"
SORTIE = RACINE / "data" / "bass" / "bass2_clean.csv"
ALERTES = RACINE / "data" / "bass" / "bass2_alertes.csv"

# ---------------------------------------------------------------------------
# 2. Les réglages
# ---------------------------------------------------------------------------
PSI_ID = "PSI-25"
DOI = "10.60555/4qc4-de67"

# Les colonnes sont renommées par POSITION (leurs noms d'origine contiennent des
# espaces en trop et changent d'un fichier à l'autre).
NOUVEAUX_NOMS = [
    "pi_name",
    "test_id",
    "test_date",
    "gmt_day_of_year",
    "sample_raw",
    "material_raw",
    "flow_restrictor",
    "fan_display_raw",
    "air_display_raw",
    "radiometer_gain_raw",
    "total_frames_raw",
    "o2_initial_pct",
    "o2_final_pct",
    "co2_initial_pct",
    "co2_final_pct",
    "co_initial_ppm",
    "co_final_ppm",
]
COLONNES_POURCENT = {
    "o2_initial_pct": "o2_initial_mole_fraction",
    "o2_final_pct": "o2_final_mole_fraction",
    "co2_initial_pct": "co2_initial_mole_fraction",
    "co2_final_pct": "co2_final_mole_fraction",
}
COLONNES_CO = ["co_initial_ppm", "co_final_ppm"]
ORDRE_FINAL = [
    "experiment_code",
    "test_id",
    "pi_name",
    "test_date",
    "gmt_day_of_year",
    "sample_id",
    "sample_raw",
    "material_raw",
    "material_family",
    "shape",
    "flow_restrictor",
    "fan_display_raw",
    "air_display_raw",
    "radiometer_gain_raw",
    "total_frames",
    "total_frames_raw",
    "o2_initial_mole_fraction",
    "o2_final_mole_fraction",
    "co2_initial_mole_fraction",
    "co2_final_mole_fraction",
    "co_initial_ppm",
    "co_initial_flag",
    "co_final_ppm",
    "co_final_flag",
    "gravity",
    "source_psi",
    "source_doi",
]

alertes = []  # la liste des points à vérifier


def noter(ligne, colonne, probleme, action):
    """Ajoute une ligne dans la liste des alertes."""
    alertes.append(
        {
            "test_id": df.loc[ligne, "test_id"],
            "colonne": colonne,
            "probleme": probleme,
            "action": action,
        }
    )


def famille(texte):
    """Matériau, seulement s'il est écrit dans la description (on ne devine rien)."""
    t = texte.lower()
    for mot, nom in [("pmma", "PMMA"), ("sibal", "SIBAL"), ("nomex", "Nomex")]:
        if mot in t:
            return nom
    return None


def forme(texte):
    """Forme de l'échantillon, seulement si elle est écrite dans la description."""
    t = texte.lower()
    for mot, nom in [
        ("rod", "rod"),
        ("film", "film"),
        ("spherical", "spherical section"),
    ]:
        if mot in t:
            return nom
    return None


def separer(colonne):
    """Sépare une colonne en nombre et en texte (le texte est gardé, sauf « none »)."""
    texte = colonne.str.strip()
    nombre = pd.to_numeric(texte, errors="coerce")
    a_garder = nombre.isna() & texte.notna() & (texte.str.lower() != "none")
    return nombre, texte.where(a_garder)


# ---------------------------------------------------------------------------
# 3. Lecture du fichier brut
# ---------------------------------------------------------------------------
# dtype=str : tout est lu comme du texte, pour voir toutes les particularités.
df = pd.read_csv(ENTREE, encoding="utf-8-sig", dtype=str)
assert len(df.columns) == len(NOUVEAUX_NOMS), "nombre de colonnes inattendu"
df.columns = NOUVEAUX_NOMS
lignes_brutes = len(df)

# ---------------------------------------------------------------------------
# 4. Textes : espaces, échantillon, matériau
# ---------------------------------------------------------------------------
for colonne in [
    "pi_name",
    "test_id",
    "sample_raw",
    "material_raw",
    "fan_display_raw",
    "air_display_raw",
    "radiometer_gain_raw",
    "total_frames_raw",
    "flow_restrictor",
]:
    df[colonne] = df[colonne].str.replace(r"\s+", " ", regex=True).str.strip()

# Le numéro d'échantillon se termine parfois par une lettre (153m, 39M, 819L) : on la retire.
df["sample_id"] = df["sample_raw"].str.extract(r"^(\d+)", expand=False)
df["material_family"] = df["material_raw"].map(famille)
df["shape"] = df["material_raw"].map(forme)
df["flow_restrictor"] = pd.to_numeric(df["flow_restrictor"], errors="coerce").astype("Int64")

# ---------------------------------------------------------------------------
# 5. Dates
# ---------------------------------------------------------------------------
# Mois/jour/année. Le jour GMT est le numéro du jour dans l'année (50 = 19 février).
date_brute = df["test_date"].str.strip()
dates = pd.to_datetime(date_brute, format="%m/%d/%Y", errors="coerce")
dates = dates.fillna(pd.to_datetime(date_brute, format="%m/%d/%y", errors="coerce"))
for i in df.index[dates.isna()]:
    noter(i, "test_date", f"date illisible « {date_brute[i]} »", "mise à vide")
df["test_date"] = dates.dt.strftime("%Y-%m-%d")
df["gmt_day_of_year"] = pd.to_numeric(df["gmt_day_of_year"], errors="coerce").astype("Int64")
ecart = df["gmt_day_of_year"] != dates.dt.day_of_year
for i in df.index[ecart.fillna(False)]:
    noter(
        i,
        "gmt_day_of_year",
        f"jour GMT {df.loc[i, 'gmt_day_of_year']} ≠ date",
        "à vérifier",
    )

# ---------------------------------------------------------------------------
# 6. Gaz : pourcentages en fractions, monoxyde de carbone avec ses drapeaux
# ---------------------------------------------------------------------------
for ancien, nouveau in COLONNES_POURCENT.items():
    nombre, texte = separer(df[ancien])
    for i in df.index[texte.notna()]:
        noter(i, ancien, f"valeur non numérique « {texte[i]} »", "mise à vide")
    # % en volume = % en moles pour un mélange de gaz parfaits : on divise par 100.
    df[nouveau] = (nombre / 100).round(5)

for colonne in COLONNES_CO:
    nombre, texte = separer(df[colonne])
    df[colonne] = nombre
    df[colonne.replace("_ppm", "_flag")] = texte  # par exemple « OR », « over », « >500 »

# ---------------------------------------------------------------------------
# 7. Nombre d'images, gravité, source
# ---------------------------------------------------------------------------
df["total_frames"] = pd.to_numeric(df["total_frames_raw"], errors="coerce").astype("Int64")
df["experiment_code"] = "BASS-II"
df["gravity"] = "microgravity"  # BASS-II a été réalisé sur l'ISS
df["source_psi"] = PSI_ID
df["source_doi"] = DOI

# ---------------------------------------------------------------------------
# 8. Contrôles qui ne modifient rien : on signale seulement
# ---------------------------------------------------------------------------
for i in df.index[df["test_id"].duplicated(keep=False)]:
    noter(i, "test_id", f"identifiant « {df.loc[i, 'test_id']} » en double", "à vérifier")

# ---------------------------------------------------------------------------
# 9. Sauvegarde
# ---------------------------------------------------------------------------
SORTIE.parent.mkdir(parents=True, exist_ok=True)
df[ORDRE_FINAL].to_csv(SORTIE, index=False, encoding="utf-8")
colonnes_alertes = ["test_id", "colonne", "probleme", "action"]
pd.DataFrame(alertes, columns=colonnes_alertes).to_csv(ALERTES, index=False, encoding="utf-8")

# ---------------------------------------------------------------------------
# 10. Petit compte rendu à l'écran
# ---------------------------------------------------------------------------
print(f"Lignes lues         : {lignes_brutes}")
print(f"Alertes             : {len(alertes)} (voir {ALERTES.name})")
print("Matériaux           :", df["material_family"].value_counts(dropna=False).to_dict())
print("Formes              :", df["shape"].value_counts(dropna=False).to_dict())
print(f"Matériau non précisé: {df['material_family'].isna().sum()} lignes (laissé vide)")
print(f"CO négatifs gardés  : {int((df[COLONNES_CO] < 0).sum().sum())} (décalage du capteur)")
print(f"Fichier propre      : {SORTIE}")
