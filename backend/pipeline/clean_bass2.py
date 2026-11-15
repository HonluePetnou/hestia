"""Clean the BASS-II test table downloaded from PSI (investigation PSI-25).

Run from the backend folder:
    uv run python -m pipeline.clean_bass2

Input  : data/psi/BASS-II/test_matrix.csv   (raw file, never modified)
Outputs: data/bass/bass2_clean.csv          (clean table)
         data/bass/bass2_alerts.csv         (points to check by hand)
"""

from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# 1. File paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]  # the "hestia" folder
INPUT = ROOT / "data" / "psi" / "BASS-II" / "test_matrix.csv"
OUTPUT = ROOT / "data" / "bass" / "bass2_clean.csv"
ALERTS = ROOT / "data" / "bass" / "bass2_alerts.csv"

# ---------------------------------------------------------------------------
# 2. Settings
# ---------------------------------------------------------------------------
PSI_ID = "PSI-25"
DOI = "10.60555/4qc4-de67"

# Columns are renamed by POSITION (the original headers have stray spaces and
# change from one file to another).
NEW_NAMES = [
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
PERCENT_COLUMNS = {
    "o2_initial_pct": "o2_initial_mole_fraction",
    "o2_final_pct": "o2_final_mole_fraction",
    "co2_initial_pct": "co2_initial_mole_fraction",
    "co2_final_pct": "co2_final_mole_fraction",
}
CO_COLUMNS = ["co_initial_ppm", "co_final_ppm"]
FINAL_ORDER = [
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

alerts = []  # points to check


def flag(row, column, problem, action):
    """Add one line to the alerts list."""
    alerts.append(
        {
            "test_id": df.loc[row, "test_id"],
            "column": column,
            "problem": problem,
            "action": action,
        }
    )


def family(text):
    """Material, only when the description states it (nothing is guessed)."""
    t = text.lower()
    for word, name in [("pmma", "PMMA"), ("sibal", "SIBAL"), ("nomex", "Nomex")]:
        if word in t:
            return name
    return None


def shape(text):
    """Sample shape, only when the description states it."""
    t = text.lower()
    for word, name in [
        ("rod", "rod"),
        ("film", "film"),
        ("spherical", "spherical section"),
    ]:
        if word in t:
            return name
    return None


def split(column):
    """Split a column into a number and a text (text kept, except 'none')."""
    text = column.str.strip()
    number = pd.to_numeric(text, errors="coerce")
    keep = number.isna() & text.notna() & (text.str.lower() != "none")
    return number, text.where(keep)


# ---------------------------------------------------------------------------
# 3. Read the raw file
# ---------------------------------------------------------------------------
# dtype=str: everything is read as text, so every oddity stays visible.
df = pd.read_csv(INPUT, encoding="utf-8-sig", dtype=str)
assert len(df.columns) == len(NEW_NAMES), "unexpected number of columns"
df.columns = NEW_NAMES
raw_rows = len(df)

# ---------------------------------------------------------------------------
# 4. Text: spaces, sample, material
# ---------------------------------------------------------------------------
for column in [
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
    df[column] = df[column].str.replace(r"\s+", " ", regex=True).str.strip()

# Sample numbers sometimes end with a letter (153m, 39M, 819L): it is dropped.
df["sample_id"] = df["sample_raw"].str.extract(r"^(\d+)", expand=False)
df["material_family"] = df["material_raw"].map(family)
df["shape"] = df["material_raw"].map(shape)
df["flow_restrictor"] = pd.to_numeric(df["flow_restrictor"], errors="coerce").astype("Int64")

# ---------------------------------------------------------------------------
# 5. Dates
# ---------------------------------------------------------------------------
# Month/day/year. The GMT day is the day number within the year (50 = 19 February).
raw_date = df["test_date"].str.strip()
dates = pd.to_datetime(raw_date, format="%m/%d/%Y", errors="coerce")
dates = dates.fillna(pd.to_datetime(raw_date, format="%m/%d/%y", errors="coerce"))
for i in df.index[dates.isna()]:
    flag(i, "test_date", f"unreadable date '{raw_date[i]}'", "set to empty")
df["test_date"] = dates.dt.strftime("%Y-%m-%d")
df["gmt_day_of_year"] = pd.to_numeric(df["gmt_day_of_year"], errors="coerce").astype("Int64")
mismatch = df["gmt_day_of_year"] != dates.dt.day_of_year
for i in df.index[mismatch.fillna(False)]:
    flag(i, "gmt_day_of_year", f"GMT day {df.loc[i, 'gmt_day_of_year']} ≠ date", "to check")

# ---------------------------------------------------------------------------
# 6. Gases: percentages to fractions, carbon monoxide with its flags
# ---------------------------------------------------------------------------
for old, new in PERCENT_COLUMNS.items():
    number, text = split(df[old])
    for i in df.index[text.notna()]:
        flag(i, old, f"non-numeric value '{text[i]}'", "set to empty")
    # Volume % = mole % for an ideal gas mixture: divide by 100.
    df[new] = (number / 100).round(5)

for column in CO_COLUMNS:
    number, text = split(df[column])
    df[column] = number
    df[column.replace("_ppm", "_flag")] = text  # e.g. "OR", "over", ">500"

# ---------------------------------------------------------------------------
# 7. Frame count, gravity, source
# ---------------------------------------------------------------------------
df["total_frames"] = pd.to_numeric(df["total_frames_raw"], errors="coerce").astype("Int64")
df["experiment_code"] = "BASS-II"
df["gravity"] = "microgravity"  # BASS-II ran on the ISS
df["source_psi"] = PSI_ID
df["source_doi"] = DOI

# ---------------------------------------------------------------------------
# 8. Checks that change nothing: report only
# ---------------------------------------------------------------------------
for i in df.index[df["test_id"].duplicated(keep=False)]:
    flag(i, "test_id", f"duplicate id '{df.loc[i, 'test_id']}'", "to check")

# ---------------------------------------------------------------------------
# 9. Save
# ---------------------------------------------------------------------------
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
df[FINAL_ORDER].to_csv(OUTPUT, index=False, encoding="utf-8")
alert_columns = ["test_id", "column", "problem", "action"]
pd.DataFrame(alerts, columns=alert_columns).to_csv(ALERTS, index=False, encoding="utf-8")

# ---------------------------------------------------------------------------
# 10. Short summary
# ---------------------------------------------------------------------------
print(f"Rows read           : {raw_rows}")
print(f"Alerts              : {len(alerts)} (see {ALERTS.name})")
print("Materials           :", df["material_family"].value_counts(dropna=False).to_dict())
print("Shapes              :", df["shape"].value_counts(dropna=False).to_dict())
print(f"Material not stated : {df['material_family'].isna().sum()} rows (left empty)")
print(f"Negative CO kept    : {int((df[CO_COLUMNS] < 0).sum().sum())} (sensor offset)")
print(f"Clean file          : {OUTPUT}")
