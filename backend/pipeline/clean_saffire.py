"""Nettoyage des tableaux d'essais SAFFIRE-1, -2 et -3 téléchargés sur PSI.

Dans ces tableaux, les unités sont écrites dans les cellules (« 29 cm », « 80 W »)
et certaines valeurs sont approchées (« ~ 21.5 ») ou textuelles (« Insignificant »).
Le script sépare le nombre de son unité, convertit vers les unités du projet et garde
le texte d'origine dans les colonnes *_raw. Il n'invente jamais de valeur.

Lancer depuis le dossier backend :
    uv run python -m pipeline.clean_saffire

Entrées : data/psi/SAFFIRE-1|2|3/test_matrix.csv   (fichiers bruts, jamais modifiés)
Sorties : data/saffire/saffire_clean.csv           (tableau propre, 3 expériences)
          data/saffire/saffire_alertes.csv         (points à vérifier à la main)
"""

import re
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# 1. Les chemins des fichiers
# ---------------------------------------------------------------------------
RACINE = Path(__file__).resolve().parents[2]  # le dossier "hestia"
DOSSIER_PSI = RACINE / "data" / "psi"
SORTIE = RACINE / "data" / "saffire" / "saffire_clean.csv"
ALERTES = RACINE / "data" / "saffire" / "saffire_alertes.csv"

# ---------------------------------------------------------------------------
# 2. Les réglages
# ---------------------------------------------------------------------------
# Les colonnes sont renommées par POSITION (les en-têtes ont des fautes et des espaces).
BASE = [
    "sample_id",
    "material_raw",
    "thickness_raw",
    "length_raw",
    "width_raw",
    "air_flow_raw",
]
EXPERIENCES = {
    "SAFFIRE-1": {
        "psi_id": "PSI-98",
        "doi": None,  # métadonnées non téléchargées : à compléter
        "colonnes": BASE
        + ["o2_raw", "ignition_power_raw", "ignition_time_raw", "burn_time_raw"]
        + ["flow_direction", "camera_1", "camera_2"],
        # Unités écrites dans les en-têtes, utilisées quand la cellule n'en a pas.
        "unites": {
            "thickness": "cm",
            "length": "cm",
            "width": "cm",
            "air_flow": "cm/s",
        },
    },
    "SAFFIRE-2": {
        "psi_id": "PSI-99",
        "doi": "10.60555/2chp-m469",
        "colonnes": BASE
        + ["o2_raw", "ignition_power_raw", "ignition_time_raw", "burn_time_raw"]
        + ["flow_direction", "burn_length_microgravity_raw", "spread_microgravity_raw"]
        + ["burn_length_1g_raw", "spread_rate_1g_raw", "camera_1", "camera_2"],
        "unites": {"width": "cm", "air_flow": "cm/s"},
    },
    "SAFFIRE-3": {
        "psi_id": "PSI-100",
        "doi": "10.60555/040q-4h36",
        "colonnes": BASE + ["flow_direction", "camera_1", "camera_2"],
        "unites": {},
    },
}
# Grandeur : (unité du projet, conversions vers cette unité)
GRANDEURS = {
    "thickness": ("mm", {"mm": 1.0, "cm": 10.0}),
    "length": ("cm", {"cm": 1.0, "mm": 0.1}),
    "width": ("cm", {"cm": 1.0, "mm": 0.1}),
    "air_flow": ("cm/s", {"cm/s": 1.0}),
    "ignition_power": ("W", {"w": 1.0}),
    "ignition_time": ("s", {"s": 1.0}),
    "burn_time": ("s", {"s": 1.0}),
}
UNITES_PAR_DEFAUT_GLOBAL = {
    "ignition_power": "w",
    "ignition_time": "s",
    "burn_time": "s",
}
MOTIF_MESURE = re.compile(r"^(~)?\s*(\d*\.?\d+)\s*([A-Za-z/]*)$")
MOTIF_O2 = re.compile(r"^(~)?\s*(\d+\.?\d*)\s*(?:-|to)?\s*(\d+\.?\d*)?$")
MOTIF_ESSAI = re.compile(r"^(S\d+|\d+-\d+)$")  # S1, S2... ou 2-1, 2-2...
FAMILLES = [
    ("silicone", "Silicone"),
    ("sibal", "SIBAL"),
    ("cotton-fiberglass", "SIBAL"),
    ("pmma", "PMMA"),
    ("nomex", "Nomex"),
]
ORDRE_FINAL = [
    "experiment_code",
    "sample_id",
    "material_raw",
    "material_family",
    "thickness_mm",
    "length_cm",
    "width_cm",
    "air_flow_cm_s",
    "o2_mole_fraction_min",
    "o2_mole_fraction_max",
    "o2_approximate",
    "ignition_power_w",
    "ignition_time_s",
    "burn_time_s",
    "flow_direction",
    "thickness_raw",
    "length_raw",
    "width_raw",
    "o2_raw",
    "burn_time_raw",
    "burn_length_microgravity_raw",
    "spread_microgravity_raw",
    "burn_length_1g_raw",
    "spread_rate_1g_raw",
    "gravity",
    "source_psi",
    "source_doi",
]

alertes = []  # la liste des points à vérifier


def noter(experience, sample, colonne, probleme, action):
    """Ajoute une ligne dans la liste des alertes."""
    alertes.append(
        {
            "experiment_code": experience,
            "sample_id": sample,
            "colonne": colonne,
            "probleme": probleme,
            "action": action,
        }
    )


def lire_mesure(texte, grandeur, unite_en_tete):
    """Sépare « 29 cm » en 29 (converti vers l'unité du projet). Renvoie (valeur, problème)."""
    if pd.isna(texte):
        return None, None
    m = MOTIF_MESURE.match(texte.strip())
    if m is None:
        return None, "texte non numérique"
    nombre, unite = m.group(2), m.group(3).lower() or unite_en_tete
    if re.match(r"^0\d+$", nombre):
        return None, f"zéro initial suspect (« {nombre} » : 0.{nombre[1:]} ?)"
    conversions = GRANDEURS[grandeur][1]
    if unite not in conversions:
        return None, f"unité absente ou inconnue (« {unite} »)"
    return round(float(nombre) * conversions[unite], 4), None


def lire_o2(texte):
    """« 21.5 - 21.7 », « ~ 22.1 » ou « 22.1 to 22.0 » en (min, max, approché)."""
    if pd.isna(texte):
        return None, None, None
    m = MOTIF_O2.match(texte.strip())
    if m is None:
        return None, None, None
    a = float(m.group(2))
    b = float(m.group(3)) if m.group(3) else a
    return min(a, b) / 100, max(a, b) / 100, m.group(1) is not None


# ---------------------------------------------------------------------------
# 3. Lecture et nettoyage de chaque expérience
# ---------------------------------------------------------------------------
tables = []
lignes_lues = 0
for code, reglage in EXPERIENCES.items():
    brut = pd.read_csv(DOSSIER_PSI / code / "test_matrix.csv", encoding="utf-8-sig", dtype=str)
    assert len(brut.columns) == len(reglage["colonnes"]), f"{code} : colonnes inattendues"
    brut.columns = reglage["colonnes"]
    lignes_lues += len(brut)
    for colonne in brut.columns:
        brut[colonne] = brut[colonne].str.replace(r"\s+", " ", regex=True).str.strip()

    # On ne garde que les vrais essais (pas les notes ni les données de visualisation).
    est_essai = brut["sample_id"].fillna("").map(lambda s: bool(MOTIF_ESSAI.match(s)))
    for i in brut.index[~est_essai]:
        noter(
            code,
            str(brut.loc[i, "sample_id"])[:40],
            "sample_id",
            "ligne qui n'est pas un essai",
            "ignorée",
        )
    df = brut[est_essai].copy()

    # Nombres et unités.
    for grandeur, (unite_projet, _) in GRANDEURS.items():
        source = f"{grandeur}_raw"
        if source not in df.columns:
            continue
        defaut = reglage["unites"].get(grandeur) or UNITES_PAR_DEFAUT_GLOBAL.get(grandeur)
        valeurs = []
        for i in df.index:
            valeur, probleme = lire_mesure(df.loc[i, source], grandeur, defaut)
            texte = df.loc[i, source]
            if probleme and pd.notna(texte) and re.search(r"\d", texte):
                noter(
                    code,
                    df.loc[i, "sample_id"],
                    source,
                    f"{probleme} : « {texte} »",
                    "mise à vide",
                )
            valeurs.append(valeur)
        suffixe = unite_projet.lower().replace("/", "_")
        df[f"{grandeur}_{suffixe}"] = valeurs

    # Oxygène (en % dans le fichier, en fraction dans le projet).
    o2 = [lire_o2(t) for t in df["o2_raw"]] if "o2_raw" in df.columns else [(None,) * 3] * len(df)
    df["o2_mole_fraction_min"] = [x[0] for x in o2]
    df["o2_mole_fraction_max"] = [x[1] for x in o2]
    df["o2_approximate"] = [x[2] for x in o2]

    df["material_family"] = df["material_raw"].map(
        lambda t: "+".join(dict.fromkeys(n for mot, n in FAMILLES if mot in str(t).lower())) or None
    )
    df["flow_direction"] = df["flow_direction"].str.lower()
    df["experiment_code"] = code
    df["gravity"] = "microgravity"  # SAFFIRE a eu lieu à bord du cargo Cygnus
    df["source_psi"] = reglage["psi_id"]
    df["source_doi"] = reglage["doi"]
    if reglage["doi"] is None:
        noter(
            code,
            None,
            "source_doi",
            "DOI inconnu (métadonnées non téléchargées)",
            "à compléter",
        )
    tables.append(df)

propre = pd.concat(tables, ignore_index=True)
for colonne in ORDRE_FINAL:
    if colonne not in propre.columns:
        propre[colonne] = None  # colonne absente de ce tableau : case vide

# ---------------------------------------------------------------------------
# 4. Sauvegarde
# ---------------------------------------------------------------------------
SORTIE.parent.mkdir(parents=True, exist_ok=True)
propre[ORDRE_FINAL].to_csv(SORTIE, index=False, encoding="utf-8")
colonnes_alertes = ["experiment_code", "sample_id", "colonne", "probleme", "action"]
pd.DataFrame(alertes, columns=colonnes_alertes).to_csv(ALERTES, index=False, encoding="utf-8")

# ---------------------------------------------------------------------------
# 5. Petit compte rendu à l'écran
# ---------------------------------------------------------------------------
print(f"Lignes lues         : {lignes_lues} (dont {len(propre)} essais)")
print(f"Alertes             : {len(alertes)} (voir {ALERTES.name})")
print("Essais par expérience:", propre["experiment_code"].value_counts().to_dict())
print(
    "Matériaux           :",
    propre["material_family"].value_counts(dropna=False).to_dict(),
)
print(f"Fichier propre      : {SORTIE}")
