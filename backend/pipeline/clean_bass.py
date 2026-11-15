"""Clean the BASS test table downloaded from PSI (investigation PSI-26).

The table only identifies the runs (date, numbers, material): it gives no test
conditions (oxygen, flow).

Run from the backend folder:
    uv run python -m pipeline.clean_bass

Input  : data/psi/BASS/test_matrix.csv   (raw file, never modified)
Outputs: data/bass/bass_clean.csv        (clean table)
         data/bass/bass_alerts.csv       (points to check by hand)
"""

from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# 1. File paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]  # the "hestia" folder
INPUT = ROOT / "data" / "psi" / "BASS" / "test_matrix.csv"
OUTPUT = ROOT / "data" / "bass" / "bass_clean.csv"
ALERTS = ROOT / "data" / "bass" / "bass_alerts.csv"

# ---------------------------------------------------------------------------
# 2. Settings
# ---------------------------------------------------------------------------
PSI_ID = "PSI-26"
DOI = "10.60555/58h4-dy80"
POSSIBLE_YEARS = range(2012, 2019)  # BASS flew roughly 2012-2014

# Columns are renamed by POSITION.
NEW_NAMES = [
    "test_date",
    "gmt_day_of_year",
    "as_run_number",
    "test_id",
    "sample_id",
    "material_raw",
]
FINAL_ORDER = [
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

# Keywords looked for in the material description (nothing else is guessed).
FAMILIES = [
    ("pmma", "PMMA"),
    ("sibal", "SIBAL"),
    ("nomex", "Nomex"),
    ("ultem", "Ultem"),
    ("wax", "Wax"),
    ("paraffin", "Wax"),
    ("parrafin", "Wax"),  # typo present in the file
]
SHAPES = [
    ("sphere", "sphere"),
    ("slab", "slab"),
    ("sheet", "sheet"),
    ("candle", "candle"),
]
FLOW_NOTES = [("wake", "wake"), ("opposed", "opposed"), ("oppsed", "opposed")]

alerts = []  # points to check


def flag(row, column, problem, action):
    """Add one line to the alerts list."""
    alerts.append(
        {
            "as_run_number": df.loc[row, "as_run_number"],
            "test_id": df.loc[row, "test_id"],
            "column": column,
            "problem": problem,
            "action": action,
        }
    )


def find(text, keywords):
    """Return the first name whose keyword appears in the text."""
    t = str(text).lower()
    for word, name in keywords:
        if word in t:
            return name
    return None


# ---------------------------------------------------------------------------
# 3. Read the raw file
# ---------------------------------------------------------------------------
df = pd.read_csv(INPUT, encoding="utf-8-sig", dtype=str)
assert len(df.columns) == len(NEW_NAMES), "unexpected number of columns"
df.columns = NEW_NAMES
raw_rows = len(df)
for column in df.columns:
    df[column] = df[column].str.replace(r"\s+", " ", regex=True).str.strip()

# ---------------------------------------------------------------------------
# 4. Numbers and material
# ---------------------------------------------------------------------------
df["as_run_number"] = pd.to_numeric(df["as_run_number"], errors="coerce").astype("Int64")
df["is_test_run"] = df["test_id"].notna()  # "SOOT Cleaning" is not a test run
df["material_family"] = df["material_raw"].map(lambda t: find(t, FAMILIES))
df["shape"] = df["material_raw"].map(lambda t: find(t, SHAPES))
df["flow_note"] = df["material_raw"].map(lambda t: find(t, FLOW_NOTES))
# Size written as "2 cm" or "1 cm" in the description (diameter or width).
df["size_cm"] = df["material_raw"].str.extract(r"(\d+(?:\.\d+)?) cm", expand=False)
df["size_cm"] = pd.to_numeric(df["size_cm"])

# ---------------------------------------------------------------------------
# 5. Dates
# ---------------------------------------------------------------------------
# Month/day/year. The GMT day is the day number within the year.
raw_date = df["test_date"]
cleaned = raw_date.str.replace("`", "", regex=False)  # "6/29/`12": typo
dates = pd.to_datetime(cleaned, format="%m/%d/%Y", errors="coerce")
dates = dates.fillna(pd.to_datetime(cleaned, format="%m/%d/%y", errors="coerce"))
for i in df.index[cleaned != raw_date]:
    flag(i, "test_date", f"date '{raw_date[i]}' read as {dates[i]:%Y-%m-%d}", "fixed")
for i in df.index[dates.isna()]:
    flag(i, "test_date", f"unreadable date '{raw_date[i]}'", "set to empty")
impossible = dates.notna() & ~dates.dt.year.isin(POSSIBLE_YEARS)
for i in df.index[impossible]:
    flag(i, "test_date", f"impossible year in '{raw_date[i]}'", "set to empty")
dates = dates.where(~impossible)
df["test_date"] = dates.dt.strftime("%Y-%m-%d")
df["gmt_day_of_year"] = pd.to_numeric(df["gmt_day_of_year"], errors="coerce").astype("Int64")
mismatch = (df["gmt_day_of_year"] != dates.dt.day_of_year) & dates.notna()
for i in df.index[mismatch.fillna(False)]:
    flag(i, "gmt_day_of_year", f"GMT day {df.loc[i, 'gmt_day_of_year']} ≠ date", "to check")

# ---------------------------------------------------------------------------
# 6. Checks that change nothing: report only
# ---------------------------------------------------------------------------
runs = df[df["is_test_run"]]
for column in ["as_run_number", "test_id"]:
    duplicates = runs[column].duplicated(keep=False) & runs[column].notna()
    for i in runs.index[duplicates]:
        flag(i, column, f"duplicate value '{df.loc[i, column]}'", "to check")

# ---------------------------------------------------------------------------
# 7. Gravity, source and save
# ---------------------------------------------------------------------------
df["experiment_code"] = "BASS"
df["gravity"] = "microgravity"  # BASS ran on the ISS
df["source_psi"] = PSI_ID
df["source_doi"] = DOI

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
df[FINAL_ORDER].to_csv(OUTPUT, index=False, encoding="utf-8")
alert_columns = ["as_run_number", "test_id", "column", "problem", "action"]
pd.DataFrame(alerts, columns=alert_columns).to_csv(ALERTS, index=False, encoding="utf-8")

# ---------------------------------------------------------------------------
# 8. Short summary
# ---------------------------------------------------------------------------
print(f"Rows read           : {raw_rows} ({int(df['is_test_run'].sum())} test runs)")
print(f"Alerts              : {len(alerts)} (see {ALERTS.name})")
print("Materials           :", df["material_family"].value_counts(dropna=False).to_dict())
print("Shapes              :", df["shape"].value_counts(dropna=False).to_dict())
print(f"Clean file          : {OUTPUT}")
