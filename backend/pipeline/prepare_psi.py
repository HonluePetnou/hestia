"""Build the data/psi/<EXPERIMENT>/ folders from the files downloaded from PSI.

For each experiment the script:
  1. copies the test table as test_matrix.csv;
  2. extracts the metadata files (i_Investigation.txt, s_PSI-xx.txt);
  3. writes a metadata.json summary (DOI, platform, PI, objective...).

Run from the backend folder, giving the folder that holds the PSI downloads:
    uv run python -m pipeline.prepare_psi "C:\\path\\to\\NASA SPACE APP CHALLENGE"
"""

import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # the "hestia" folder
DESTINATION = ROOT / "data" / "psi"

# (folder name, PSI record number that starts the file names)
EXPERIMENTS = [
    ("FLEX", "PSI-69"),
    ("FLEX-2", "PSI-68"),
    ("SAFFIRE-1", "PSI-98"),
    ("SAFFIRE-2", "PSI-99"),
    ("SAFFIRE-3", "PSI-100"),
    ("BASS", "PSI-26"),
    ("BASS-II", "PSI-25"),
]


def find(source, prefix, suffix):
    """Find a file in the source folder whose name starts with `prefix`."""
    candidates = [
        f
        for f in sorted(source.iterdir())
        if f.name.startswith(prefix) and f.name.endswith(suffix) and "(1)" not in f.name
    ]
    return candidates[0] if candidates else None


def read_fields(text):
    """Turn i_Investigation.txt into a {label: [values]} dictionary."""
    fields = {}
    for line in text.splitlines():
        parts = [m.strip().strip('"') for m in line.split("\t")]
        if len(parts) > 1 and any(parts[1:]):
            fields.setdefault(parts[0], parts[1:])
    return fields


def first(fields, label):
    """First value of a field, or None when it is missing or empty."""
    values = fields.get(label) or [None]
    return values[0] or None


def iso_date(date):
    """08-01-2007 (month-day-year) becomes 2007-08-01."""
    m = re.match(r"(\d\d)-(\d\d)-(\d{4})$", date or "")
    return f"{m.group(3)}-{m.group(1)}-{m.group(2)}" if m else date


def principal_investigator(fields):
    """Find the person whose role is Principal Investigator (PI)."""
    roles = fields.get("Study Person Roles", [])
    for i, role in enumerate(roles):
        if "Principal Investigator" in role:
            first_name = fields.get("Study Person First Name", [])[i]
            last_name = fields.get("Study Person Last Name", [])[i]
            affiliations = fields.get("Study Person Affiliation", [])
            affiliation = affiliations[i] if i < len(affiliations) else ""
            name = f"{first_name} {last_name}"
            return f"{name} ({affiliation})" if affiliation else name
    return None


def process(code, psi_id, source):
    folder = DESTINATION / code
    folder.mkdir(parents=True, exist_ok=True)

    csv = find(source, f"{psi_id}_Experimental", ".csv")
    if csv is None:
        return f"{code}: test table not found (skipped)"
    shutil.copyfile(csv, folder / "test_matrix.csv")

    archive = find(source, f"{psi_id}_metadata", ".zip")
    if archive is None:
        return f"{code}: table copied, but no metadata zip (download it from PSI)"

    with zipfile.ZipFile(archive) as zf:
        for name in zf.namelist():
            if not name.endswith("/"):
                (folder / Path(name).name).write_bytes(zf.read(name))
    text = (folder / "i_Investigation.txt").read_text(encoding="utf-8", errors="replace")
    fields = read_fields(text)

    metadata = {
        "code": code,
        "psi_id": first(fields, "Study Identifier"),
        "title": first(fields, "Study Title"),
        "doi": first(fields, "Comment[DOI]"),
        "platform": first(fields, "Comment[Flight Platform]"),
        "hardware": first(fields, "Comment[Experiment Hardware]"),
        "pi": principal_investigator(fields),
        "start_date": iso_date(first(fields, "Comment[Investigation Start Date]")),
        "end_date": iso_date(first(fields, "Comment[Investigation End Date]")),
        "objective": first(fields, "Comment[Objective]"),
        "license": "CC0",
        "source_file": f"i_Investigation.txt ({archive.name})",
    }
    with open(folder / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
        f.write("\n")
    empty = [key for key, value in metadata.items() if value is None]
    note = f" (empty fields: {', '.join(empty)})" if empty else ""
    return f"{code}: OK, DOI {metadata['doi']}{note}"


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    source = Path(sys.argv[1])
    if not source.is_dir():
        print(f"Folder not found: {source}")
        sys.exit(1)
    for code, psi_id in EXPERIMENTS:
        print(process(code, psi_id, source))
    print(f"Output in: {DESTINATION}")


if __name__ == "__main__":
    main()
