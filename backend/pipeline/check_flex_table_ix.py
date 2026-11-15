"""Check the FLEX Table IX transcription and compare it with the PSI data.

Run from the backend folder:
    uv run python -m pipeline.check_flex_table_ix

Inputs: data/flex/flex_table_ix.csv    (hand transcription of Table IX)
        data/flex/flex_psi_clean.csv   (PSI table cleaned by clean_flex.py)

The script does two things:
  1. it checks the transcription (allowed values, plausible units, sum of gases);
  2. it looks for each Table IX run in the PSI data (same fuel, pressure, oxygen and
     diameter) and compares K and the outcome.
"""

from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# 1. Paths and settings
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]  # the "hestia" folder
TABLE_IX = ROOT / "data" / "flex" / "flex_table_ix.csv"
PSI = ROOT / "data" / "flex" / "flex_psi_clean.csv"

ALLOWED_OUTCOMES = {"extinction", "disruption", "complete_burn", "unknown"}
# Plausible ranges: a value outside is probably a typo.
RANGES = {
    "pressure_atm": (0.3, 3.5),
    "o2_mole_fraction": (0.0, 1.0),
    "co2_mole_fraction": (0.0, 1.0),
    "n2_mole_fraction": (0.0, 1.0),
    "initial_diameter_mm": (0.5, 6.0),
    "burn_rate_k_mm2_s": (0.0, 2.0),
}
# Allowed gap for two runs to count as having the same conditions.
TOLERANCES = {
    "pressure_atm": 0.02,
    "o2_mole_fraction": 0.005,
    "initial_diameter_mm": 0.05,
}
K_TOLERANCE = 0.02  # allowed gap on K (mm²/s)

problems = []  # points to check

# ---------------------------------------------------------------------------
# 2. Read
# ---------------------------------------------------------------------------
if not TABLE_IX.exists():
    raise SystemExit(f"File not found: {TABLE_IX}")
table = pd.read_csv(TABLE_IX)
print(f"Table IX transcribed: {len(table)} rows")
if table.empty:
    raise SystemExit("Table IX is empty: transcribe a few rows, then run again.")

# ---------------------------------------------------------------------------
# 3. Check the transcription
# ---------------------------------------------------------------------------
bad = table[~table["outcome"].isin(ALLOWED_OUTCOMES)]
for _, row in bad.iterrows():
    problems.append(f"{row['test_id']}: outcome '{row['outcome']}' not allowed")

for column, (low, high) in RANGES.items():
    outside = table[(table[column] < low) | (table[column] > high)]
    for _, row in outside.iterrows():
        problems.append(f"{row['test_id']}: {column} = {row[column]} outside [{low}, {high}]")

# Guide 02 does not count helium: a run with helium has a sum below 1.
gases = ["o2_mole_fraction", "co2_mole_fraction", "n2_mole_fraction"]
total = table[gases].fillna(0).sum(axis=1)
for i in table.index[(total < 0.9) | (total > 1.01)]:
    problems.append(f"{table.loc[i, 'test_id']}: sum of gases = {total[i]:.2f} (helium?)")

for i in table.index[table["test_id"].duplicated(keep=False)]:
    problems.append(f"{table.loc[i, 'test_id']}: duplicate id")

# ---------------------------------------------------------------------------
# 4. Compare with the PSI data
# ---------------------------------------------------------------------------
if not PSI.exists():
    print(f"\nCannot compare: {PSI.name} is missing (run clean_flex first).")
    psi = None
else:
    psi = pd.read_csv(PSI)

found = 0
k_matches = 0
outcome_matches = 0
missing = []
if psi is not None:
    for _, run in table.iterrows():
        candidates = psi[psi["fuel"] == run["fuel"]]
        for column, tolerance in TOLERANCES.items():
            candidates = candidates[(candidates[column] - run[column]).abs() <= tolerance]
        if candidates.empty:
            missing.append(run["test_id"])
            continue
        found += 1
        k_ok = candidates["burn_rate_k_mm2_s"].sub(run["burn_rate_k_mm2_s"]).abs().le(K_TOLERANCE)
        k_matches += int(k_ok.any() or pd.isna(run["burn_rate_k_mm2_s"]))
        outcome_matches += int((candidates["outcome"] == run["outcome"]).any())

# ---------------------------------------------------------------------------
# 5. Report
# ---------------------------------------------------------------------------
print(f"\nPoints to check in the transcription: {len(problems)}")
for p in problems:
    print("  -", p)
if psi is not None:
    print("\nComparison with PSI (same test conditions):")
    print(f"  runs found in PSI      : {found} of {len(table)}")
    print(f"  same K (within {K_TOLERANCE}) : {k_matches} of {found}")
    print(f"  same outcome           : {outcome_matches} of {found}")
    if missing:
        print("  not found:", ", ".join(map(str, missing[:20])))
