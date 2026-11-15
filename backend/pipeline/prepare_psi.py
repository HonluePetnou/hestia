"""Prépare les dossiers data/psi/<EXPERIENCE>/ à partir des fichiers téléchargés sur PSI.

Pour chaque expérience, le script :
  1. copie le tableau d'essais sous le nom test_matrix.csv ;
  2. extrait les fichiers de métadonnées (i_Investigation.txt, s_PSI-xx.txt) ;
  3. écrit un résumé metadata.json (DOI, plateforme, responsable, objectif...).

Lancer depuis le dossier backend, en donnant le dossier qui contient les fichiers PSI :
    uv run python -m pipeline.prepare_psi "C:\\chemin\\vers\\NASA SPACE APP CHALLENGE"
"""

import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]  # le dossier "hestia"
DESTINATION = RACINE / "data" / "psi"

# (nom du dossier, numéro de la fiche PSI qui commence les noms de fichiers)
EXPERIENCES = [
    ("FLEX", "PSI-69"),
    ("FLEX-2", "PSI-68"),
    ("SAFFIRE-1", "PSI-98"),
    ("SAFFIRE-2", "PSI-99"),
    ("SAFFIRE-3", "PSI-100"),
    ("BASS", "PSI-26"),
    ("BASS-II", "PSI-25"),
]


def trouver(source, debut, fin):
    """Cherche dans le dossier source un fichier dont le nom commence par `debut`."""
    candidats = [
        f
        for f in sorted(source.iterdir())
        if f.name.startswith(debut) and f.name.endswith(fin) and "(1)" not in f.name
    ]
    return candidats[0] if candidats else None


def lire_champs(texte):
    """Transforme i_Investigation.txt en dictionnaire {libellé: [valeurs]}."""
    champs = {}
    for ligne in texte.splitlines():
        morceaux = [m.strip().strip('"') for m in ligne.split("\t")]
        if len(morceaux) > 1 and any(morceaux[1:]):
            champs.setdefault(morceaux[0], morceaux[1:])
    return champs


def premier(champs, libelle):
    """Première valeur d'un champ, ou None s'il est absent ou vide."""
    valeurs = champs.get(libelle) or [None]
    return valeurs[0] or None


def date_iso(date):
    """08-01-2007 (mois-jour-année) devient 2007-08-01."""
    m = re.match(r"(\d\d)-(\d\d)-(\d{4})$", date or "")
    return f"{m.group(3)}-{m.group(1)}-{m.group(2)}" if m else date


def responsable(champs):
    """Cherche la personne dont le rôle est Principal Investigator (PI)."""
    roles = champs.get("Study Person Roles", [])
    for i, role in enumerate(roles):
        if "Principal Investigator" in role:
            prenom = champs.get("Study Person First Name", [])[i]
            nom = champs.get("Study Person Last Name", [])[i]
            affiliations = champs.get("Study Person Affiliation", [])
            affiliation = affiliations[i] if i < len(affiliations) else ""
            return f"{prenom} {nom} ({affiliation})" if affiliation else f"{prenom} {nom}"
    return None


def traiter(code, psi_id, source):
    dossier = DESTINATION / code
    dossier.mkdir(parents=True, exist_ok=True)

    csv = trouver(source, f"{psi_id}_Experimental", ".csv")
    if csv is None:
        return f"{code}: tableau d'essais introuvable (ignoré)"
    shutil.copyfile(csv, dossier / "test_matrix.csv")

    archive = trouver(source, f"{psi_id}_metadata", ".zip")
    if archive is None:
        return f"{code}: tableau copié, mais pas de zip de métadonnées à télécharger sur PSI"

    with zipfile.ZipFile(archive) as zf:
        for nom in zf.namelist():
            if not nom.endswith("/"):
                (dossier / Path(nom).name).write_bytes(zf.read(nom))
    texte = (dossier / "i_Investigation.txt").read_text(encoding="utf-8", errors="replace")
    champs = lire_champs(texte)

    metadata = {
        "code": code,
        "psi_id": premier(champs, "Study Identifier"),
        "title": premier(champs, "Study Title"),
        "doi": premier(champs, "Comment[DOI]"),
        "platform": premier(champs, "Comment[Flight Platform]"),
        "hardware": premier(champs, "Comment[Experiment Hardware]"),
        "pi": responsable(champs),
        "start_date": date_iso(premier(champs, "Comment[Investigation Start Date]")),
        "end_date": date_iso(premier(champs, "Comment[Investigation End Date]")),
        "objective": premier(champs, "Comment[Objective]"),
        "license": "CC0",
        "source_file": f"i_Investigation.txt ({archive.name})",
    }
    with open(dossier / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
        f.write("\n")
    vides = [cle for cle, valeur in metadata.items() if valeur is None]
    note = f" (champs vides : {', '.join(vides)})" if vides else ""
    return f"{code}: OK, DOI {metadata['doi']}{note}"


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    source = Path(sys.argv[1])
    if not source.is_dir():
        print(f"Dossier introuvable : {source}")
        sys.exit(1)
    for code, psi_id in EXPERIENCES:
        print(traiter(code, psi_id, source))
    print(f"Résultat dans : {DESTINATION}")


if __name__ == "__main__":
    main()
