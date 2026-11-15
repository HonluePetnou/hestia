"""Clean the FLEX test table downloaded from PSI (investigation PSI-69).

Run from the backend folder:
    uv run python -m pipeline.clean_flex

Input  : data/psi/FLEX/test_matrix.csv   (raw file, never modified)
Outputs: data/flex/flex_psi_clean.csv    (clean table)
         data/flex/flex_psi_alerts.csv   (points to check by hand)
"""

from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# 1. File paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]  # the "hestia" folder
INPUT = ROOT / "data" / "psi" / "FLEX" / "test_matrix.csv"
OUTPUT = ROOT / "data" / "flex" / "flex_psi_clean.csv"
ALERTS = ROOT / "data" / "flex" / "flex_psi_alerts.csv"

# ---------------------------------------------------------------------------
# 2. Settings (every hard-coded value lives here)
# ---------------------------------------------------------------------------
PSI_ID = "PSI-69"
DOI = "10.60555/mbq8-0451"
MMHG_PER_ATM = 760.0  # 1 atm = 760 mmHg
DASHES = {"–", "—", "-"}  # signs PSI uses for "not reported"
GAS_TOLERANCE = 0.015  # allowed gap between the sum of gas fractions and 1 (rounding)

NEW_NAMES = {
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
NUMBER_COLUMNS = [
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
FUELS = {"Heptane": "n-heptane", "Methanol": "methanol"}  # to check
OUTCOMES = {
    "Extinction": "extinction",
    "Disruption": "disruption",
    "Completion": "complete_burn",
}
FINAL_ORDER = [
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

alerts = []  # points to check


def flag(row, column, problem, action):
    """Add one line to the alerts list."""
    alerts.append(
        {
            "test_number": df.loc[row, "test_number"],
            "test_id": df.loc[row, "test_id"],
            "column": column,
            "problem": problem,
            "action": action,
        }
    )


# ---------------------------------------------------------------------------
# 3. Read the raw file
# ---------------------------------------------------------------------------
# encoding="cp1252": the file is Windows-1252, not UTF-8.
# dtype=str: everything is read as text to see the "–" and the "~6".
df = pd.read_csv(INPUT, encoding="cp1252", dtype=str)
df.columns = df.columns.str.strip()
df = df.rename(columns=NEW_NAMES)
raw_rows = len(df)

# ---------------------------------------------------------------------------
# 4. Text -> numbers
# ---------------------------------------------------------------------------
n_dashes = 0
for column in NUMBER_COLUMNS:
    text = df[column].str.strip()
    number = pd.to_numeric(text, errors="coerce")
    unreadable = number.isna() & text.notna()
    for i in df.index[unreadable]:
        if text[i] in DASHES:
            n_dashes += 1
        else:
            flag(i, column, f"non-numeric value '{text[i]}'", "set to empty")
    df[column] = number
df["test_number"] = df["test_number"].astype("Int64")

# ---------------------------------------------------------------------------
# 5. Pressure: mmHg -> atm
# ---------------------------------------------------------------------------
impossible = df["pressure_mmhg"] <= 0
for i in df.index[impossible]:
    flag(i, "pressure_mmhg", "pressure of 0 mmHg (impossible)", "set to empty")
df.loc[impossible, "pressure_mmhg"] = pd.NA
df["pressure_atm"] = (df["pressure_mmhg"] / MMHG_PER_ATM).round(4)

# ---------------------------------------------------------------------------
# 6. Fuel, outcome, date, gravity, source
# ---------------------------------------------------------------------------
raw_fuel = df["fuel"].str.strip()
df["fuel"] = raw_fuel.map(FUELS)
for i in df.index[df["fuel"].isna() & raw_fuel.notna()]:
    flag(i, "fuel", f"unknown fuel '{raw_fuel[i]}'", "set to empty")

raw_outcome = df["outcome"].str.strip()
df["outcome"] = raw_outcome.map(OUTCOMES).fillna("unknown")

# Dates are month/day/year: 3/5/2009 = 5 March 2009.
# Some have a 2-digit year (10/24/09): both forms are tried.
raw_date = df["test_date"].str.strip()
dates = pd.to_datetime(raw_date, format="%m/%d/%Y", errors="coerce")
dates = dates.fillna(pd.to_datetime(raw_date, format="%m/%d/%y", errors="coerce"))
for i in df.index[dates.isna() & raw_date.notna()]:
    flag(i, "test_date", f"unreadable date '{raw_date[i]}'", "set to empty")
df["test_date"] = dates.dt.strftime("%Y-%m-%d")

df["gravity"] = "microgravity"  # FLEX ran on the ISS
df["source_psi"] = PSI_ID
df["source_doi"] = DOI

# ---------------------------------------------------------------------------
# 7. Checks that change nothing: report only
# ---------------------------------------------------------------------------
gases = ["o2_mole_fraction", "n2_mole_fraction", "co2_mole_fraction", "he_mole_fraction"]
total = df[gases].sum(axis=1)
for i in df.index[(total - 1).abs() > GAS_TOLERANCE]:
    flag(i, "gases", f"sum of fractions = {total[i]:.2f} (expected 1)", "to check")

for i in df.index[df["test_id"].duplicated(keep=False)]:
    flag(i, "test_id", f"duplicate id '{df.loc[i, 'test_id']}'", "to check")

# ---------------------------------------------------------------------------
# 8. Save
# ---------------------------------------------------------------------------
allowed = {"extinction", "disruption", "complete_burn", "unknown"}
assert df["outcome"].isin(allowed).all(), "unexpected outcome"

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
df[FINAL_ORDER].to_csv(OUTPUT, index=False, encoding="utf-8")
alert_columns = ["test_number", "test_id", "column", "problem", "action"]
pd.DataFrame(alerts, columns=alert_columns).to_csv(ALERTS, index=False, encoding="utf-8")

# ---------------------------------------------------------------------------
# 9. Short summary
# ---------------------------------------------------------------------------
print(f"Rows read           : {raw_rows}")
print(f"Dashes set to empty : {n_dashes}")
print(f"Alerts              : {len(alerts)} (see {ALERTS.name})")
print(f"K reported          : {df['burn_rate_k_mm2_s'].notna().sum()} rows")
print("Outcomes            :", df["outcome"].value_counts().to_dict())
print(f"Clean file          : {OUTPUT}")
